from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.core.deps import get_current_user
from app.db.mongo import get_collection
from app.models.knowledge_graph import MaterialKGResponse, StudentKGResponse, StudentKGStateItem
from app.services.kg_service import kg_service

router = APIRouter(prefix="/knowledge-graph", tags=["Knowledge Graph"])

@router.get("/material/{analysis_id}", response_model=MaterialKGResponse)
async def get_material_kg(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        data = await kg_service.get_material_kg(analysis_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Material KG not found: {e}")

@router.get("/student/{user_id}", response_model=StudentKGResponse)
async def get_student_kg(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Ensure student can only view their own passport/KG unless authorized
    if current_user["_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another student's graph")

    student_kg_coll = get_collection("student_kg_state")
    skill_nodes_coll = get_collection("skill_nodes")

    cursor = student_kg_coll.find({"user_id": ObjectId(user_id)})
    docs = await cursor.to_list(length=500)

    items = []
    for d in docs:
        node_doc = await skill_nodes_coll.find_one({"_id": d["node_id"]})
        display_name = node_doc.get("display_name", node_doc["name"]) if node_doc else "Unknown Node"
        items.append(StudentKGStateItem(
            node_id=str(d["node_id"]),
            display_name=display_name,
            competency_score=d.get("competency_score", 0.0),
            last_updated=d.get("last_updated", datetime.now(timezone.utc)),
            evidence_event_ids=[str(eid) for eid in d.get("evidence_event_ids", [])]
        ))

    return StudentKGResponse(
        user_id=user_id,
        skills=items
    )
