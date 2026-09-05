from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.core.deps import get_current_user
from app.db.mongo import get_collection
from app.models.assessment import QuizStartRequest, QuizSubmitRequest, AttemptResponse, InterviewStartRequest, InterviewAnswerRequest, InterviewTurnResponse
from app.services.exam_service import exam_service

router = APIRouter(prefix="/exams", tags=["Exam Module (Quiz & Interview)"])

@router.post("/quiz/start")
async def start_exam_quiz(
    body: QuizStartRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        data = await exam_service.create_exam_quiz(
            user_id_str=current_user["_id"],
            resource_id_str=body.resource_id
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/quiz/{assessment_id}/submit", response_model=AttemptResponse)
async def submit_exam_quiz(
    assessment_id: str,
    body: QuizSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        attempt_data = await exam_service.submit_exam_quiz(
            user_id_str=current_user["_id"],
            assessment_id_str=assessment_id,
            user_answers=[a.model_dump() for a in body.answers]
        )
        return attempt_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/interview/start", response_model=InterviewTurnResponse)
async def start_interview(
    body: InterviewStartRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        turn = await exam_service.start_interview(
            user_id_str=current_user["_id"],
            resource_id_str=body.resource_id
        )
        return turn
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/interview/{session_id}/answer", response_model=InterviewTurnResponse)
async def answer_interview(
    session_id: str,
    body: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        turn = await exam_service.answer_interview_turn(
            user_id_str=current_user["_id"],
            session_id_str=session_id,
            answer_text=body.answer
        )
        return turn
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/interview/history/{user_id}")
async def get_interview_history(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user["_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another student's history")

    interviews_coll = get_collection("interview_sessions")
    cursor = interviews_coll.find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)

    history = []
    for d in docs:
        history.append({
            "session_id": str(d["_id"]),
            "resource_id": str(d["resource_id"]),
            "status": d.get("status", "completed"),
            "turns_count": len(d.get("turns", [])),
            "turns": d.get("turns", []),
            "created_at": d.get("created_at", datetime.now(timezone.utc))
        })

    return history
