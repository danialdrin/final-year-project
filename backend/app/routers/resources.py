from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from bson import ObjectId
from app.core.deps import get_current_user
from app.db.mongo import get_collection
from app.models.resource import ResourceResponse, MediumAnalysisScores
from app.services.pdf_service import pdf_service
from app.services.strong_analysis_service import strong_analysis_service

router = APIRouter(prefix="/resources", tags=["Resources & Upload"])

@router.post("/{resource_id}/select")
async def select_resource(
    resource_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    resources_coll = get_collection("resources")
    jobs_coll = get_collection("jobs")

    try:
        r_id = ObjectId(resource_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid resource_id")

    resource = await resources_coll.find_one({"_id": r_id, "user_id": ObjectId(current_user["_id"])})
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    # Update resource status
    await resources_coll.update_one(
        {"_id": r_id},
        {"$set": {"status": "selected", "updated_at": datetime.now(timezone.utc)}}
    )

    # Create background job doc
    job_doc = {
        "type": "strong_analysis",
        "user_id": ObjectId(current_user["_id"]),
        "resource_id": r_id,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    res_job = await jobs_coll.insert_one(job_doc)
    job_id_str = str(res_job.inserted_id)

    # Dispatch background task
    background_tasks.add_task(
        strong_analysis_service.run_analysis_task,
        job_id_str=job_id_str,
        resource_id_str=resource_id
    )

    return {
        "resource_id": resource_id,
        "status": "selected",
        "job_id": job_id_str,
        "message": "Resource selected. Strong Analysis job started in background."
    }

@router.post("/upload")
async def upload_resource(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    if not file and not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide either a file or a url")

    resources_coll = get_collection("resources")
    jobs_coll = get_collection("jobs")
    user_id_obj = ObjectId(current_user["_id"])

    if file:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")
        
        file_bytes = await file.read()
        full_text, pages = pdf_service.extract_text_from_bytes(file_bytes)

        resource_doc = {
            "user_id": user_id_obj,
            "source_type": "pdf",
            "url_or_file": file.filename,
            "title": file.filename,
            "status": "selected",
            "raw_text": full_text,
            "pages": pages,
            "medium_analysis": None,
            "created_at": datetime.now(timezone.utc)
        }
    else:
        resource_doc = {
            "user_id": user_id_obj,
            "source_type": "youtube",
            "url_or_file": url,
            "title": f"YouTube Resource ({url})",
            "status": "selected",
            "medium_analysis": None,
            "created_at": datetime.now(timezone.utc)
        }

    res_res = await resources_coll.insert_one(resource_doc)
    resource_id_str = str(res_res.inserted_id)

    # Create job doc
    job_doc = {
        "type": "strong_analysis",
        "user_id": user_id_obj,
        "resource_id": res_res.inserted_id,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    res_job = await jobs_coll.insert_one(job_doc)
    job_id_str = str(res_job.inserted_id)

    # Dispatch background task
    background_tasks.add_task(
        strong_analysis_service.run_analysis_task,
        job_id_str=job_id_str,
        resource_id_str=resource_id_str
    )

    return {
        "resource_id": resource_id_str,
        "title": resource_doc["title"],
        "status": "selected",
        "job_id": job_id_str,
        "message": "Resource uploaded. Strong Analysis started directly (skipping Medium Analysis)."
    }

@router.get("", response_model=list[ResourceResponse])
async def list_resources(current_user: dict = Depends(get_current_user)):
    resources_coll = get_collection("resources")
    cursor = resources_coll.find({"user_id": ObjectId(current_user["_id"])}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)

    res_list = []
    for d in docs:
        ma = d.get("medium_analysis")
        res_list.append(ResourceResponse(
            resource_id=str(d["_id"]),
            user_id=str(d["user_id"]),
            source_type=d.get("source_type", "youtube"),
            url_or_file=d.get("url_or_file", ""),
            title=d.get("title", ""),
            status=d.get("status", "pending"),
            medium_analysis=MediumAnalysisScores(**ma) if ma else None,
            created_at=d.get("created_at", datetime.now(timezone.utc))
        ))
    return res_list
