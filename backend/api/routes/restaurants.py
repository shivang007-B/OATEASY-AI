from fastapi import APIRouter
from backend.db.database import get_db

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])

@router.get("")
def list_restaurants():
    """List available restaurants in the system"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM restaurants ORDER BY restaurant_id")
        rows = [dict(r) for r in cursor.fetchall()]
    return {"restaurants": rows}
