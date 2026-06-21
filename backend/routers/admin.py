from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.user import User
from backend.dependencies import get_current_user
from backend.services.drift_monitor import compute_drift_metrics, check_drift_alert

router = APIRouter(prefix="/admin", tags=["Admin"])

async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires administrator privileges"
        )
    return current_user

@router.get("/drift-report", summary="Get model drift report")
async def get_drift_report(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    metrics = await compute_drift_metrics(db)
    alert = check_drift_alert(metrics["current"], metrics["previous"])
    
    return {
        "metrics": metrics,
        "alert": alert
    }
