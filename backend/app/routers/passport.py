from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.core.deps import get_current_user
from app.db.mongo import get_collection
from app.models.passport import PassportResponse, PassportNodeItem, GapRecommendationResponse, GapItem

router = APIRouter(prefix="/passport", tags=["Digital Skill Passport"])

@router.get("/{user_id}", response_model=PassportResponse)
async def get_passport(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user["_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another student's passport")

    student_kg_coll = get_collection("student_kg_state")
    skill_nodes_coll = get_collection("skill_nodes")

    cursor = student_kg_coll.find({"user_id": ObjectId(user_id)})
    state_docs = await cursor.to_list(length=500)

    passport_nodes = []
    latest_update = datetime.now(timezone.utc)

    for doc in state_docs:
        node_doc = await skill_nodes_coll.find_one({"_id": doc["node_id"]})
        display_name = node_doc.get("display_name", node_doc["name"]) if node_doc else "Unknown Skill"
        desc = node_doc.get("description") if node_doc else None
        bloom = node_doc.get("bloom_level") if node_doc else None

        updated_at = doc.get("last_updated", datetime.now(timezone.utc))

        passport_nodes.append(PassportNodeItem(
            node_id=str(doc["node_id"]),
            display_name=display_name,
            description=desc,
            bloom_level=bloom,
            competency_score=doc.get("competency_score", 0.0),
            last_updated=updated_at,
            evidence_event_ids=[str(eid) for eid in doc.get("evidence_event_ids", [])]
        ))

    return PassportResponse(
        user_id=user_id,
        nodes=passport_nodes,
        updated_at=latest_update
    )

@router.get("/{user_id}/gaps", response_model=GapRecommendationResponse)
async def get_passport_gaps(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user["_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another student's passport gaps")

    student_kg_coll = get_collection("student_kg_state")
    skill_nodes_coll = get_collection("skill_nodes")
    kg_edges_coll = get_collection("kg_edges")

    # Find nodes with evidence where competency_score < 60
    cursor = student_kg_coll.find({
        "user_id": ObjectId(user_id),
        "competency_score": {"$lt": 60.0}
    })
    gap_docs = await cursor.to_list(length=100)

    gaps = []
    for doc in gap_docs:
        node_id = doc["node_id"]
        node_doc = await skill_nodes_coll.find_one({"_id": node_id})
        display_name = node_doc.get("display_name", node_doc["name"]) if node_doc else "Unknown Node"

        # Walk prerequisite edges backward
        prereq_edges_cursor = kg_edges_coll.find({"to_node_id": node_id, "relation": "prerequisite"})
        prereq_edges = await prereq_edges_cursor.to_list(length=20)
        
        prereq_names = []
        for edge in prereq_edges:
            prereq_node = await skill_nodes_coll.find_one({"_id": edge["from_node_id"]})
            if prereq_node:
                prereq_names.append(prereq_node.get("display_name", prereq_node["name"]))

        gaps.append(GapItem(
            node_id=str(node_id),
            display_name=display_name,
            competency_score=doc.get("competency_score", 0.0),
            recommended_prerequisites=prereq_names
        ))

    return GapRecommendationResponse(
        user_id=user_id,
        gaps=gaps
    )
