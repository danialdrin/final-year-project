from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class SkillNodeSchema(BaseModel):
    node_id: str
    name: str
    display_name: str
    description: Optional[str] = None
    type: str = "concept"  # "concept" | "skill"
    bloom_level: Optional[str] = None
    parent_id: Optional[str] = None
    prerequisite_ids: List[str] = Field(default_factory=list)

class KGEdgeSchema(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation: str  # "prerequisite" | "part_of" | "related_to"
    material_id: Optional[str] = None

class MaterialKGResponse(BaseModel):
    analysis_id: str
    nodes: List[SkillNodeSchema]
    edges: List[KGEdgeSchema]

class StudentKGStateItem(BaseModel):
    node_id: str
    display_name: str
    competency_score: float
    last_updated: datetime
    evidence_event_ids: List[str]

class StudentKGResponse(BaseModel):
    user_id: str
    skills: List[StudentKGStateItem]
