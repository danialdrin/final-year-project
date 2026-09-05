from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class QuestionSchema(BaseModel):
    question_id: str
    type: str  # "mcq" | "short_answer" | "code_explain"
    prompt: str
    options: Optional[List[str]] = None
    node_id: str
    target_bloom: Optional[str] = "apply"

class QuizStartRequest(BaseModel):
    resource_id: str

class QuestionAnswerSubmit(BaseModel):
    question_id: str
    user_answer: str

class QuizSubmitRequest(BaseModel):
    answers: List[QuestionAnswerSubmit]

class QuestionResultItem(BaseModel):
    question_id: str
    raw_score: float  # 0.0 to 1.0
    feedback: str
    node_id: str

class AttemptResponse(BaseModel):
    attempt_id: str
    assessment_id: str
    user_id: str
    score: float  # 0 to 100
    per_question_result: List[QuestionResultItem]
    created_at: datetime

class InterviewStartRequest(BaseModel):
    resource_id: str

class InterviewAnswerRequest(BaseModel):
    answer: str

class InterviewTurnResponse(BaseModel):
    session_id: str
    turn_index: int
    question: Optional[str] = None
    evaluation: Optional[QuestionResultItem] = None
    status: str  # "in_progress" | "completed"
