
import logging
import traceback
from typing import Dict, Any, List
from datetime import datetime, timezone
from pydantic import ValidationError
from bson import ObjectId
from app.db.mongo import get_collection
from app.services.transcript_service import transcript_service
from app.services.llm_service import llm_service
from app.models.analysis import StrongAnalysisResultSchema, ConceptSchema, TopicSchema, RelationshipSchema, ImportantSectionSchema
from app.services.kg_service import kg_service
from app.utils.json_extract import JSONExtractionError

logger = logging.getLogger(__name__)

MAX_ANALYSIS_INPUT = 10000
REQUIRED_ANALYSIS_KEYS = {"topics", "concepts", "relationships", "important_sections"}

STRONG_ANALYSIS_PROMPT = """
Perform deep semantic educational analysis on the following learning text content.
Return ONLY one strict JSON object matching this schema. Do not use Markdown fences, explanations, comments, trailing commas, or text before or after the object. Use double quotes for all keys and string values, escape embedded quotes, separate every property with a comma, and close every array and object.

{{
  "topics": [
    {{
      "topic": "Main Topic Name",
      "subtopics": ["Subtopic 1", "Subtopic 2"],
      "difficulty": "beginner|intermediate|advanced",
      "skills": ["skill name 1", "skill name 2"],
      "learning_outcomes": ["outcome 1"]
    }}
  ],
  "concepts": [
    {{
      "name": "Concept Name",
      "definition": "Clear concise definition",
      "examples": ["example 1", "example 2"],
      "prerequisites": ["Prerequisite Concept Name"],
      "bloom_level": "remember|understand|apply|analyze|evaluate|create",
      "difficulty": "beginner|intermediate|advanced",
      "timestamp_or_page": "timestamp or page reference if available"
    }}
  ],
  "relationships": [
    {{
      "from": "Source Concept Name",
      "to": "Target Concept Name",
      "relation": "prerequisite|part_of|related_to"
    }}
  ],
  "important_sections": [
    {{
      "title": "Section Title",
      "timestamp_or_page": "timestamp or page",
      "why_important": "Reason for importance"
    }}
  ]
}}

Content:
{content}
"""

JSON_CORRECTION_PROMPT = """
The previous response was not valid for the required Strong Analysis schema.
Return ONLY a corrected JSON object matching the exact schema in the original prompt.
Do not include Markdown fences, explanations, comments, trailing commas, or any text outside the JSON object.
Correct the JSON syntax and include every required field, even when its value is an empty array.
"""

class StrongAnalysisService:
    async def run_analysis_task(self, job_id_str: str, resource_id_str: str):
        jobs_coll = get_collection("jobs")
        resources_coll = get_collection("resources")
        analyses_coll = get_collection("analyses")

        try:
            await jobs_coll.update_one(
                {"_id": ObjectId(job_id_str)},
                {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc)}}
            )

            resource = await resources_coll.find_one({"_id": ObjectId(resource_id_str)})
            if not resource:
                raise Exception(f"Resource {resource_id_str} not found")

            # Extract raw text
            source_type = resource.get("source_type")
            url_or_file = resource.get("url_or_file", "")
            raw_text = ""

            if source_type == "youtube":
                # Extract video ID from URL or url_or_file
                video_id = url_or_file
                if "v=" in url_or_file:
                    video_id = url_or_file.split("v=")[1].split("&")[0]
                elif "youtu.be/" in url_or_file:
                    video_id = url_or_file.split("youtu.be/")[1].split("?")[0]
                
                full_text, _, _ = transcript_service.get_transcript(video_id)
                raw_text = full_text if full_text else f"{resource.get('title')} {url_or_file}"
            elif source_type == "pdf":
                raw_text = resource.get("raw_text", resource.get("title", ""))

            if not raw_text.strip():
                raw_text = resource.get("title", "Educational Content")

            # Bound the prompt before the single analysis request.
            analysis_text = raw_text[:MAX_ANALYSIS_INPUT]
            prompt = STRONG_ANALYSIS_PROMPT.format(content=analysis_text)
            validation_error = None
            for attempt_prompt in (prompt, JSON_CORRECTION_PROMPT):
                try:
                    json_res = await llm_service.call_llm(attempt_prompt, expect_json=True)
                    if not isinstance(json_res, dict):
                        raise ValueError("Strong Analysis response must be a JSON object.")
                    if "analysis" in json_res and isinstance(json_res["analysis"], dict):
                        json_res = json_res["analysis"]
                    missing_keys = REQUIRED_ANALYSIS_KEYS - json_res.keys()
                    if missing_keys:
                        raise ValueError(f"Strong Analysis response is missing fields: {sorted(missing_keys)}")
                    validated = StrongAnalysisResultSchema.model_validate(json_res)
                    break
                except (JSONExtractionError, ValidationError, ValueError) as error:
                    validation_error = error
                    logger.warning(
                        "Strong Analysis structured-output validation failure attempt=%s error_type=%s",
                        1 if attempt_prompt == prompt else 2,
                        type(error).__name__,
                    )
                    continue
                except Exception:
                    raise
            else:
                raise ValueError(f"Strong Analysis JSON validation failed after one correction retry: {validation_error}") from validation_error

            all_topics = [t.model_dump() for t in validated.topics]
            all_concepts = [c.model_dump() for c in validated.concepts]
            all_relationships = [r.model_dump(by_alias=True) for r in validated.relationships]
            all_sections = [s.model_dump() for s in validated.important_sections]

            # Deduplicate concepts by normalized name
            dedup_concepts = {}
            for c in all_concepts:
                norm_name = c["name"].strip().lower()
                if norm_name not in dedup_concepts:
                    dedup_concepts[norm_name] = c

            merged_data = {
                "topics": all_topics,
                "concepts": list(dedup_concepts.values()),
                "relationships": all_relationships,
                "important_sections": all_sections
            }

            # Insert into analyses collection
            analysis_doc = {
                "resource_id": ObjectId(resource_id_str),
                "transcript_or_text": raw_text[:5000],  # store snippet or text
                "version": 1,
                "extracted_data": merged_data,
                "created_at": datetime.now(timezone.utc)
            }
            res_analysis = await analyses_coll.insert_one(analysis_doc)
            analysis_id = res_analysis.inserted_id

            # Build Material Knowledge Graph
            await kg_service.build_material_kg(analysis_id=analysis_id, extracted_data=merged_data)

            # Update resource status
            await resources_coll.update_one(
                {"_id": ObjectId(resource_id_str)},
                {"$set": {"status": "strong_analyzed"}}
            )

            # Update job status
            await jobs_coll.update_one(
                {"_id": ObjectId(job_id_str)},
                {"$set": {
                    "status": "done",
                    "result": {"analysis_id": str(analysis_id), "resource_id": resource_id_str},
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

        except Exception as e:
            err_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Strong Analysis Job {job_id_str} failed: {err_msg}")
            await jobs_coll.update_one(
                {"_id": ObjectId(job_id_str)},
                {"$set": {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

strong_analysis_service = StrongAnalysisService()

