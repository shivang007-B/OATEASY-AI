from fastapi import APIRouter, Query
from typing import Optional
from backend.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])
report_service = ReportService()

@router.get("/latest")
def get_latest_report(restaurant_id: Optional[str] = Query(None, description="Restaurant ID (R01, R02, or all)")):
    """Load the latest generated daily intelligence report"""
    return report_service.get_latest_report(restaurant_id=restaurant_id)

@router.post("/generate")
def generate_report(planning_date: Optional[str] = Query(None, description="Target planning date (YYYY-MM-DD)")):
    """Request a fresh analysis and regenerate reports via ML models"""
    return report_service.generate_daily_report(planning_date=planning_date)
