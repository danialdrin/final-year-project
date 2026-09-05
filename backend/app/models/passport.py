from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class PassportNodeItem(BaseModel):
    node_id: str
    display_name: str
    description: Optional[str] = None
    bloom_level: Optional[str] = None
    competency_score: float
    last_updated: datetime
    evidence_event_ids: List[str]

class PassportResponse(BaseModel):
    user_id: str
    nodes: List[PassportNodeItem]
    updated_at: datetime

class GapItem(BaseModel):
    node_id: str
    display_name: str
    competency_score: float
    recommended_prerequisites: List[str]

class GapRecommendationResponse(BaseModel):
    user_id: str
    gaps: List[GapItem]
