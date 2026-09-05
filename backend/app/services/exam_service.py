import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from app.db.mongo import get_collection
from app.services.llm_service import llm_service
from app.services.competency_service import competency_service

logger = logging.getLogger(__name__)

QUIZ_GEN_PROMPT = """
Generate {num_questions} quiz questions for the following concepts.
Adjust question difficulty according to the requested difficulty level: {difficulty_level}.

Concepts to test:
{concepts_text}

Return a strict JSON object with this shape:
{{
  "questions": [
    {{
      "question_id": "q1",
      "type": "mcq|short_answer|code_explain",
      "prompt": "Question text...",
      "options": ["Option A", "Option B", "Option C", "Option D"],  // null for short_answer
      "correct_answer": "Option A or key expected points",
      "concept_name": "Target Concept Name",
      "target_bloom": "remember|understand|apply|analyze|evaluate|create"
    }}
  ]
}}
"""

SHORT_ANSWER_GRADE_PROMPT = """
Grade the student's answer for the following question.
Question: {prompt}
Expected / Target Answer: {expected_answer}
Student Answer: {student_answer}

Provide a strict JSON evaluation with:
- "raw_score": float between 0.0 and 1.0 (allow partial credit)
- "feedback": "Short constructive feedback explanation"
"""

INTERVIEW_QUESTION_PROMPT = """
You are an expert technical interviewer conducting a mock interview for learning resource concepts:
{concepts_text}

Previous Interview Turns:
{history_text}

Generate the NEXT interview question to test the student's depth of understanding.
Keep the question clear, engaging, and focused on core concepts.
Return JSON:
{{
  "question": "Interview question text...",
  "target_concept": "Concept Name"
}}
"""

INTERVIEW_EVAL_PROMPT = """
Evaluate the candidate's response in this technical interview.
Question: {question}
Candidate Answer: {answer}

Provide a strict JSON evaluation:
{{
  "raw_score": float between 0.0 and 1.0,
  "feedback": "Short evaluation and constructive tips"
}}
"""

class ExamService:
    async def create_exam_quiz(self, user_id_str: str, resource_id_str: str) -> Dict[str, Any]:
        user_id = ObjectId(user_id_str)
        resource_id = ObjectId(resource_id_str)

        analyses_coll = get_collection("analyses")
        student_kg_coll = get_collection("student_kg_state")
        skill_nodes_coll = get_collection("skill_nodes")
        assessments_coll = get_collection("assessments")

        analysis = await analyses_coll.find_one({"resource_id": resource_id})
        if not analysis:
            raise Exception("No analysis found for this resource. Run Strong Analysis first.")

        concepts = analysis.get("extracted_data", {}).get("concepts", [])
        if not concepts:
            concepts = [{"name": "General Knowledge", "definition": "General topic overview"}]

        # Determine target difficulty based on student's average competency on these concepts
        concept_names = [c["name"].strip().lower() for c in concepts]
        nodes_cursor = skill_nodes_coll.find({"name": {"$in": concept_names}})
        nodes_docs = await nodes_cursor.to_list(length=100)
        node_ids = [n["_id"] for n in nodes_docs]

        states_cursor = student_kg_coll.find({"user_id": user_id, "node_id": {"$in": node_ids}})
        states = await states_cursor.to_list(length=100)

        if states:
            avg_score = sum(s["competency_score"] for s in states) / len(states)
            if avg_score > 80:
                difficulty = "advanced"
            elif avg_score >= 50:
                difficulty = "intermediate"
            else:
                difficulty = "beginner"
        else:
            difficulty = "beginner"

        concepts_text = "\n".join([f"- {c['name']}: {c.get('definition', '')}" for c in concepts[:5]])
        prompt = QUIZ_GEN_PROMPT.format(num_questions=3, difficulty_level=difficulty, concepts_text=concepts_text)
        
        json_res = await llm_service.call_llm(prompt, expect_json=True)
        raw_questions = json_res.get("questions", [])

        processed_questions = []
        for idx, q in enumerate(raw_questions):
            c_name = q.get("concept_name", "").strip().lower()
            node_doc = await skill_nodes_coll.find_one({"name": c_name})
            if not node_doc and nodes_docs:
                node_doc = nodes_docs[0]
            
            node_id_str = str(node_doc["_id"]) if node_doc else str(ObjectId())

            processed_questions.append({
                "question_id": f"q_{idx+1}",
                "type": q.get("type", "mcq"),
                "prompt": q.get("prompt", ""),
                "options": q.get("options"),
                "correct_answer": q.get("correct_answer", ""),
                "node_id": node_id_str,
                "target_bloom": q.get("target_bloom", "apply")
            })

        assessment_doc = {
            "user_id": user_id,
            "resource_id": resource_id,
            "type": "quiz",
            "questions": processed_questions,
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        }
        res = await assessments_coll.insert_one(assessment_doc)
        assessment_id = str(res.inserted_id)

        # Return questions to client WITHOUT correct_answer
        client_questions = [
            {
                "question_id": q["question_id"],
                "type": q["type"],
                "prompt": q["prompt"],
                "options": q.get("options"),
                "node_id": q["node_id"],
                "target_bloom": q.get("target_bloom")
            }
            for q in processed_questions
        ]

        return {
            "assessment_id": assessment_id,
            "questions": client_questions
        }

    async def submit_exam_quiz(self, user_id_str: str, assessment_id_str: str, user_answers: List[Dict[str, str]]) -> Dict[str, Any]:
        user_id = ObjectId(user_id_str)
        assessment_id = ObjectId(assessment_id_str)

        assessments_coll = get_collection("assessments")
        attempts_coll = get_collection("attempts")

        assessment = await assessments_coll.find_one({"_id": assessment_id, "user_id": user_id})
        if not assessment:
            raise Exception("Assessment not found")

        q_map = {q["question_id"]: q for q in assessment.get("questions", [])}
        user_ans_map = {a["question_id"]: a["user_answer"] for a in user_answers}

        per_question_results = []
        total_raw_score = 0.0

        attempt_doc_placeholder = await attempts_coll.insert_one({
            "assessment_id": assessment_id,
            "user_id": user_id,
            "status": "evaluating",
            "created_at": datetime.now(timezone.utc)
        })
        attempt_id_str = str(attempt_doc_placeholder.inserted_id)

        for q_id, q_data in q_map.items():
            user_ans = user_ans_map.get(q_id, "").strip()
            q_type = q_data.get("type", "mcq")
            correct_ans = q_data.get("correct_answer", "")
            node_id_str = q_data.get("node_id")

            if q_type == "mcq":
                if user_ans.lower() == correct_ans.lower() or (len(user_ans) == 1 and correct_ans.lower().startswith(user_ans.lower())):
                    raw_score = 1.0
                    feedback = "Correct choice!"
                else:
                    raw_score = 0.0
                    feedback = f"Incorrect. Correct answer: {correct_ans}"
            else:
                prompt = SHORT_ANSWER_GRADE_PROMPT.format(
                    prompt=q_data["prompt"],
                    expected_answer=correct_ans,
                    student_answer=user_ans
                )
                try:
                    eval_res = await llm_service.call_llm(prompt, expect_json=True)
                    raw_score = float(eval_res.get("raw_score", 0.5))
                    feedback = eval_res.get("feedback", "Evaluated")
                except Exception:
                    raw_score = 0.5
                    feedback = "Partial credit awarded."

            raw_score = max(0.0, min(1.0, raw_score))
            total_raw_score += raw_score
            per_question_results.append({
                "question_id": q_id,
                "raw_score": raw_score,
                "feedback": feedback,
                "node_id": node_id_str
            })

            # Record competency event
            if node_id_str:
                await competency_service.record_competency_event(
                    user_id_str=user_id_str,
                    node_id_str=node_id_str,
                    source="quiz",
                    raw_score=raw_score,
                    ref_id_str=attempt_id_str
                )

        final_score = round((total_raw_score / max(len(q_map), 1)) * 100.0, 2)

        # Update attempt doc
        await attempts_coll.update_one(
            {"_id": ObjectId(attempt_id_str)},
            {"$set": {
                "answers": user_answers,
                "score": final_score,
                "per_question_result": per_question_results,
                "status": "completed"
            }}
        )

        return {
            "attempt_id": attempt_id_str,
            "assessment_id": assessment_id_str,
            "user_id": user_id_str,
            "score": final_score,
            "per_question_result": per_question_results,
            "created_at": datetime.now(timezone.utc)
        }

    async def start_interview(self, user_id_str: str, resource_id_str: str) -> Dict[str, Any]:
        user_id = ObjectId(user_id_str)
        resource_id = ObjectId(resource_id_str)

        analyses_coll = get_collection("analyses")
        interviews_coll = get_collection("interview_sessions")

        analysis = await analyses_coll.find_one({"resource_id": resource_id})
        if not analysis:
            raise Exception("No analysis found for this resource.")

        concepts = analysis.get("extracted_data", {}).get("concepts", [])
        concepts_text = "\n".join([f"- {c['name']}: {c.get('definition', '')}" for c in concepts[:5]])

        prompt = INTERVIEW_QUESTION_PROMPT.format(concepts_text=concepts_text, history_text="None")
        json_res = await llm_service.call_llm(prompt, expect_json=True)
        first_q = json_res.get("question", "Tell me about what you learned from this material.")

        doc = {
            "user_id": user_id,
            "resource_id": resource_id,
            "turns": [],
            "current_question": first_q,
            "status": "in_progress",
            "created_at": datetime.now(timezone.utc)
        }
        res = await interviews_coll.insert_one(doc)
        session_id = str(res.inserted_id)

        return {
            "session_id": session_id,
            "turn_index": 1,
            "question": first_q,
            "status": "in_progress"
        }

    async def answer_interview_turn(self, user_id_str: str, session_id_str: str, answer_text: str) -> Dict[str, Any]:
        session_id = ObjectId(session_id_str)
        interviews_coll = get_collection("interview_sessions")
        analyses_coll = get_collection("analyses")
        skill_nodes_coll = get_collection("skill_nodes")

        session = await interviews_coll.find_one({"_id": session_id, "user_id": ObjectId(user_id_str)})
        if not session or session.get("status") != "in_progress":
            raise Exception("Active interview session not found")

        current_q = session.get("current_question", "Explain key concepts.")
        turns = session.get("turns", [])
        turn_idx = len(turns) + 1

        # Evaluate candidate answer
        eval_prompt = INTERVIEW_EVAL_PROMPT.format(question=current_q, answer=answer_text)
        json_eval = await llm_service.call_llm(eval_prompt, expect_json=True)

        raw_score = float(json_eval.get("raw_score", 0.7))
        feedback = json_eval.get("feedback", "Good explanation.")

        # Find default concept node to attach evidence to
        node_doc = await skill_nodes_coll.find_one({})
        node_id_str = str(node_doc["_id"]) if node_doc else str(ObjectId())

        await competency_service.record_competency_event(
            user_id_str=user_id_str,
            node_id_str=node_id_str,
            source="interview",
            raw_score=raw_score,
            ref_id_str=session_id_str
        )

        turn_obj = {
            "turn_index": turn_idx,
            "question": current_q,
            "answer": answer_text,
            "evaluation": {
                "question_id": f"turn_{turn_idx}",
                "raw_score": raw_score,
                "feedback": feedback,
                "node_id": node_id_str
            },
            "ts": datetime.now(timezone.utc)
        }

        # Generate next question or conclude
        if turn_idx >= 5:
            next_q = None
            status_str = "completed"
        else:
            analysis = await analyses_coll.find_one({"resource_id": session["resource_id"]})
            concepts = analysis.get("extracted_data", {}).get("concepts", []) if analysis else []
            concepts_text = "\n".join([f"- {c['name']}" for c in concepts])
            history_text = "\n".join([f"Q: {t['question']}\nA: {t['answer']}" for t in turns + [turn_obj]])

            next_prompt = INTERVIEW_QUESTION_PROMPT.format(concepts_text=concepts_text, history_text=history_text)
            next_json = await llm_service.call_llm(next_prompt, expect_json=True)
            next_q = next_json.get("question", "Can you expand further on practical implementation details?")
            status_str = "in_progress"

        await interviews_coll.update_one(
            {"_id": session_id},
            {
                "$push": {"turns": turn_obj},
                "$set": {
                    "current_question": next_q,
                    "status": status_str,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        return {
            "session_id": session_id_str,
            "turn_index": turn_idx,
            "question": next_q,
            "evaluation": turn_obj["evaluation"],
            "status": status_str
        }

exam_service = ExamService()
