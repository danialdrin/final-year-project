import logging
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
from app.db.mongo import get_collection

logger = logging.getLogger(__name__)

def calculate_ema_score(old_score: Optional[float], raw_score: float, alpha: float = 0.4) -> float:
    """
    Exponential Moving Average calculation for competency scores.
    raw_score is between 0.0 and 1.0.
    Returns new competency score between 0.0 and 100.0.
    """
    event_score_100 = raw_score * 100.0
    if old_score is None:
        return round(event_score_100, 2)
    
    new_score = alpha * event_score_100 + (1.0 - alpha) * old_score
    return round(new_score, 2)

class CompetencyService:
    async def record_competency_event(
        self,
        user_id_str: str,
        node_id_str: str,
        source: str,  # "quiz" | "interview"
        raw_score: float,  # 0.0 to 1.0
        ref_id_str: str,
        weight: float = 1.0
    ) -> str:
        user_id = ObjectId(user_id_str)
        node_id = ObjectId(node_id_str)
        ref_id = ObjectId(ref_id_str)

        events_coll = get_collection("competency_events")
        student_kg_coll = get_collection("student_kg_state")

        # 1. Insert immutable competency event
        event_doc = {
            "user_id": user_id,
            "node_id": node_id,
            "source": source,
            "raw_score": raw_score,
            "weight": weight,
            "ref_id": ref_id,
            "created_at": datetime.now(timezone.utc)
        }
        res_event = await events_coll.insert_one(event_doc)
        event_id = res_event.inserted_id

        # 2. Fetch existing student KG state
        state_doc = await student_kg_coll.find_one({"user_id": user_id, "node_id": node_id})
        old_score = state_doc["competency_score"] if state_doc else None

        new_score = calculate_ema_score(old_score, raw_score)

        # 3. Upsert student KG state
        if state_doc:
            await student_kg_coll.update_one(
                {"_id": state_doc["_id"]},
                {
                    "$set": {
                        "competency_score": new_score,
                        "last_updated": datetime.now(timezone.utc)
                    },
                    "$addToSet": {"evidence_event_ids": event_id}
                }
            )
        else:
            new_state_doc = {
                "user_id": user_id,
                "node_id": node_id,
                "competency_score": new_score,
                "last_updated": datetime.now(timezone.utc),
                "evidence_event_ids": [event_id]
            }
            await student_kg_coll.insert_one(new_state_doc)

        return str(event_id)

competency_service = CompetencyService()
