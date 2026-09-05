from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.core.deps import get_current_user
from app.db.mongo import get_collection
from app.models.analysis import JobResponse, AnalysisResponse, StrongAnalysisResultSchema

router = APIRouter(tags=["Analysis & Jobs"])

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    jobs_coll = get_collection("jobs")
    try:
        j_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = await jobs_coll.find_one({"_id": j_id, "user_id": ObjectId(current_user["_id"])})
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobResponse(
        job_id=str(job["_id"]),
        type=job.get("type", "strong_analysis"),
        status=job.get("status", "queued"),
        result=job.get("result"),
        error=job.get("error"),
        created_at=job.get("created_at", datetime.now(timezone.utc))
    )

@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    analyses_coll = get_collection("analyses")
    try:
        a_id = ObjectId(analysis_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid analysis_id")

    analysis = await analyses_coll.find_one({"_id": a_id})
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    extracted = analysis.get("extracted_data", {})
    validated_schema = StrongAnalysisResultSchema.model_validate(extracted)

    return AnalysisResponse(
        analysis_id=str(analysis["_id"]),
        resource_id=str(analysis["resource_id"]),
        transcript_or_text=analysis.get("transcript_or_text", ""),
        version=analysis.get("version", 1),
        extracted_data=validated_schema,
        created_at=analysis.get("created_at", datetime.now(timezone.utc))
    )
