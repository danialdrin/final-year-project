import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.core.deps import get_current_user, get_redis
from app.db.mongo import get_collection
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["Interactive Modules"])

SUMMARY_PROMPT = """
Summarize the following learning content into clear bullet points with main takeaways:
Content:
{content}

Return JSON:
{{
  "title": "Resource Summary",
  "summary_points": ["Point 1", "Point 2", "Point 3"],
  "key_takeaway": "Main takeaway..."
}}
"""

FLASHCARD_PROMPT = """
Generate 5 flashcards (question and concise answer) from this content:
Content:
{content}

Return JSON:
{{
  "flashcards": [
    {{ "front": "Question / Concept", "back": "Clear answer / definition" }}
  ]
}}
"""

PRACTICE_QUIZ_PROMPT = """
Generate 4 practice quiz questions (casual study quiz) for this content:
Content:
{content}

Return JSON:
{{
  "quiz": [
    {{ "question": "...", "options": ["A", "B", "C", "D"], "answer": "Option A", "explanation": "..." }}
  ]
}}
"""

async def get_analysis_for_resource(resource_id_str: str):
    resources_coll = get_collection("resources")
    analyses_coll = get_collection("analyses")
    try:
        r_id = ObjectId(resource_id_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid resource_id")

    resource = await resources_coll.find_one({"_id": r_id})
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    analysis = await analyses_coll.find_one({"resource_id": r_id})
    if not analysis:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resource not analyzed yet. Run Strong Analysis first.")

    return str(analysis["_id"]), analysis.get("version", 1), analysis.get("transcript_or_text", "")

@router.get("/{resource_id}/summary")
async def get_summary(
    resource_id: str,
    current_user: dict = Depends(get_current_user),
    redis_client = Depends(get_redis)
):
    analysis_id_str, version, text = await get_analysis_for_resource(resource_id)
    cache_key = f"summary:{analysis_id_str}:{version}"

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read error: {e}")

    # Generate via the centralized Groq LLM service
    prompt = SUMMARY_PROMPT.format(content=text[:4000])
    res = await llm_service.call_llm(prompt, expect_json=True)

    try:
        await redis_client.set(cache_key, json.dumps(res), ex=604800)
    except Exception as e:
        logger.warning(f"Redis cache write error: {e}")

    return res

@router.get("/{resource_id}/flashcards")
async def get_flashcards(
    resource_id: str,
    current_user: dict = Depends(get_current_user),
    redis_client = Depends(get_redis)
):
    analysis_id_str, version, text = await get_analysis_for_resource(resource_id)
    cache_key = f"flashcards:{analysis_id_str}:{version}"

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read error: {e}")

    prompt = FLASHCARD_PROMPT.format(content=text[:4000])
    res = await llm_service.call_llm(prompt, expect_json=True)

    try:
        await redis_client.set(cache_key, json.dumps(res), ex=604800)
    except Exception as e:
        logger.warning(f"Redis cache write error: {e}")

    return res

@router.get("/{resource_id}/quiz")
async def get_practice_quiz(
    resource_id: str,
    current_user: dict = Depends(get_current_user),
    redis_client = Depends(get_redis)
):
    analysis_id_str, version, text = await get_analysis_for_resource(resource_id)
    cache_key = f"quiz:{analysis_id_str}:{version}"

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read error: {e}")

    prompt = PRACTICE_QUIZ_PROMPT.format(content=text[:4000])
    res = await llm_service.call_llm(prompt, expect_json=True)

    try:
        await redis_client.set(cache_key, json.dumps(res), ex=604800)
    except Exception as e:
        logger.warning(f"Redis cache write error: {e}")

    return res
