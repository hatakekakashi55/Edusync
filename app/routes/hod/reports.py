"""
EduSync Backend - HOD - Reports Routes
Modularized and deduplicated.
"""
import logging
import os
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, Form, Query, Body
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

from app.dependencies import verify_token, convert_objectid_to_str
from app.database import *
from app.models.auth import UserType
from app.models.report import ReportStatus, ReportType, ReportSchedule
from app.services.notification_service import NotificationService
from app.utils.helpers import generate_department_report, get_reports_by_type, get_reports_by_status, get_recently_generated, get_reports_trend

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/hod/reports", tags=["HOD - Reports"])

@router.get("/stats", tags=["HOD - Reports"])
async def get_report_stats(current_user: dict = Depends(verify_token)):
    """Get report statistics for HOD dashboard"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        counts = {
            "total": await reports_collection.count_documents({"department": department}),
            "by_type": await get_reports_by_type(department),
            "by_status": await get_reports_by_status(department)
        }
        
        return {
            "success": True,
            "statistics": counts
        }
    except Exception as e:
        logger.error(f"Get report stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", tags=["HOD - Reports"])
async def list_reports(
    report_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """List all generated reports for department"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
            
        query = {"department": current_user["department"]}
        if report_type:
            query["type"] = report_type
        if status:
            query["status"] = status
            
        reports = await reports_collection.find(query) \
            .sort("generated_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
            
        return {
            "success": True,
            "reports": convert_objectid_to_str(reports),
            "total": await reports_collection.count_documents(query)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate", tags=["HOD - Reports"])
async def generate_report_endpoint(
    report_type: str = Form("monthly"),
    format: str = Form("pdf"),
    current_user: dict = Depends(verify_token)
):
    """Generate a new department report"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
            
        dept = current_user["department"]
        report_data = await generate_department_report(dept, report_type)
        
        if not report_data:
             raise HTTPException(status_code=500, detail="Generation failed")
             
        # Log to DB
        report_doc = {
            "title": f"{dept} {report_type.capitalize()} Report",
            "type": report_type,
            "department": dept,
            "format": format,
            "status": "generated",
            "generated_by": str(current_user["_id"]),
            "generated_at": datetime.now(timezone.utc),
            "data": report_data
        }
        
        result = await reports_collection.insert_one(report_doc)
        
        return {
            "success": True,
            "report_id": str(result.inserted_id),
            "message": "Report generated successfully"
        }
    except Exception as e:
        logger.error(f"Generate report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{report_id}/download", tags=["HOD - Reports"])
async def download_report_file(
    report_id: str,
    current_user: dict = Depends(verify_token)
):
    """Download report file"""
    try:
        report = await reports_collection.find_one({"_id": ObjectId(report_id)})
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
            
        # Simulated downloader
        return {"success": True, "download_url": f"/files/reports/{report_id}.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
