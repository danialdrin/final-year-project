from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TopicSchema(BaseModel):
    topic: str
    subtopics: List[str] = Field(default_factory=list)
    difficulty: str = "intermediate"
    skills: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)

class ConceptSchema(BaseModel):
    name: str
    definition: str
    examples: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    bloom_level: str = "understand"
    difficulty: str = "intermediate"
    timestamp_or_page: Optional[str] = None

class RelationshipSchema(BaseModel):
    from_concept: str = Field(..., alias="from")
    to_concept: str = Field(..., alias="to")
    relation: str = "prerequisite"  # "prerequisite" | "part_of" | "related_to"

    class Config:
        populate_by_name = True

class ImportantSectionSchema(BaseModel):
    title: str
    timestamp_or_page: Optional[str] = None
    why_important: str

class StrongAnalysisResultSchema(BaseModel):
    topics: List[TopicSchema] = Field(default_factory=list)
    concepts: List[ConceptSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)
    important_sections: List[ImportantSectionSchema] = Field(default_factory=list)

class AnalysisResponse(BaseModel):
    analysis_id: str
    resource_id: str
    transcript_or_text: str
    version: int
    extracted_data: StrongAnalysisResultSchema
    created_at: datetime

class JobResponse(BaseModel):
    job_id: str
    type: str
    status: str  # "queued" | "processing" | "done" | "failed"
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
