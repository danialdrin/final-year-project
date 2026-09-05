from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    page_token: Optional[str] = None

class MediumAnalysisScores(BaseModel):
    relevance: float = 0.0
    topic_coverage: float = 0.0
    depth: float = 0.0
    examples: float = 0.0
    clarity: float = 0.0
    structure: float = 0.0
    redundancy: float = 0.0
    overall: float = 0.0
    transcript_available: bool = True

class ResourceResponse(BaseModel):
    resource_id: str
    user_id: Optional[str] = None
    source_type: str  # "youtube" | "pdf"
    url_or_file: str
    title: str
    status: str  # "pending" | "medium_analyzed" | "selected" | "strong_analyzed"
    medium_analysis: Optional[MediumAnalysisScores] = None
    created_at: datetime

class CandidateResourceResponse(BaseModel):
    resource_id: str
    video_id: str
    title: str
    channel: str
    thumbnail: str
    description: str = ""
    is_mock: bool = False
    medium_analysis: Optional[MediumAnalysisScores] = None

class SearchResponse(BaseModel):
    candidates: List[CandidateResourceResponse]
    next_page_token: Optional[str] = None
