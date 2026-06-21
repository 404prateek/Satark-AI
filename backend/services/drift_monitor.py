"""
Satark AI Drift Monitor
=======================

HONEST LIMITATIONS:
This is a lightweight, proxy-metric drift monitoring system that uses user 
feedback and raw score aggregates as an early-warning signal. It is NOT a 
statistical drift-detection algorithm (like autoencoder reconstruction error 
or KS-tests on embeddings) commonly found in academic research or mature MLOps 
platforms. 

Why use this?
It's highly practical for an early-stage product. It catches the most common 
failure modes (e.g., attackers changing their templates, causing average 
confidence to drop or user corrections to spike) without the overhead of a 
complex ML pipeline. Once there is enough scan volume to make statistical 
methods meaningful, this system provides a clear upgrade path.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scan import Scan, Verdict
from backend.models.feedback import ScanFeedback

logger = logging.getLogger(__name__)

async def compute_drift_metrics(db: AsyncSession, window_days: int = 7) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)

    async def get_metrics_for_window(start: datetime, end: datetime) -> dict[str, Any]:
        # Average confidence for PHISHING verdicts
        stmt_conf = select(func.avg(Scan.confidence)).where(
            and_(Scan.created_at >= start, Scan.created_at < end, Scan.verdict == Verdict.PHISHING)
        )
        avg_conf = await db.scalar(stmt_conf)
        
        # Count verdicts
        stmt_verdicts = select(Scan.verdict, func.count(Scan.id)).where(
            and_(Scan.created_at >= start, Scan.created_at < end)
        ).group_by(Scan.verdict)
        verdict_counts_raw = await db.execute(stmt_verdicts)
        verdict_counts = {v: c for v, c in verdict_counts_raw.all()}
        
        total_scans = sum(verdict_counts.values())
        
        safe_count = verdict_counts.get(Verdict.SAFE, 0)
        suspicious_count = verdict_counts.get(Verdict.SUSPICIOUS, 0)
        phishing_count = verdict_counts.get(Verdict.PHISHING, 0)
        flagged_count = suspicious_count + phishing_count
        
        # Count user corrections
        stmt_fp = select(func.count(ScanFeedback.id)).where(
            and_(
                ScanFeedback.created_at >= start, 
                ScanFeedback.created_at < end, 
                ScanFeedback.user_correction == "false_positive"
            )
        )
        fp_count = await db.scalar(stmt_fp) or 0
        
        stmt_fn = select(func.count(ScanFeedback.id)).where(
            and_(
                ScanFeedback.created_at >= start, 
                ScanFeedback.created_at < end, 
                ScanFeedback.user_correction == "false_negative"
            )
        )
        fn_count = await db.scalar(stmt_fn) or 0
        
        fp_rate = (fp_count / flagged_count) if flagged_count > 0 else 0.0
        fn_rate = (fn_count / safe_count) if safe_count > 0 else 0.0
        
        return {
            "average_confidence": float(avg_conf) if avg_conf is not None else 0.0,
            "false_positive_rate": fp_rate,
            "false_negative_rate": fn_rate,
            "verdict_distribution": {
                "SAFE": (safe_count / total_scans) if total_scans > 0 else 0.0,
                "SUSPICIOUS": (suspicious_count / total_scans) if total_scans > 0 else 0.0,
                "PHISHING": (phishing_count / total_scans) if total_scans > 0 else 0.0,
            },
            "total_scans": total_scans,
        }

    current = await get_metrics_for_window(current_start, now)
    previous = await get_metrics_for_window(previous_start, current_start)
    
    return {
        "current": current,
        "previous": previous,
        "delta": {
            "average_confidence": current["average_confidence"] - previous["average_confidence"],
            "false_positive_rate": current["false_positive_rate"] - previous["false_positive_rate"],
            "false_negative_rate": current["false_negative_rate"] - previous["false_negative_rate"],
        }
    }

def check_drift_alert(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    
    # False positive rate increased by > 5 percentage points
    if current["false_positive_rate"] - previous["false_positive_rate"] > 0.05:
        reasons.append(f"False positive rate increased by >5% (from {previous['false_positive_rate']:.1%} to {current['false_positive_rate']:.1%})")
        
    # False negative rate increased by > 5 percentage points
    if current["false_negative_rate"] - previous["false_negative_rate"] > 0.05:
        reasons.append(f"False negative rate increased by >5% (from {previous['false_negative_rate']:.1%} to {current['false_negative_rate']:.1%})")
        
    # Average confidence on PHISHING dropped by > 10% (absolute drop of >0.10)
    if previous["average_confidence"] > 0 and (previous["average_confidence"] - current["average_confidence"]) > 0.10:
        reasons.append(f"Average confidence on PHISHING dropped by >10% (from {previous['average_confidence']:.2f} to {current['average_confidence']:.2f})")
        
    return {
        "alert": len(reasons) > 0,
        "reasons": reasons
    }
