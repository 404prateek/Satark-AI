import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.config import get_settings
from backend.models.database import Base, engine
from backend.models.user import User
from backend.models.scan import Scan, Verdict, ScanInputType
from backend.services.auth_service import hash_password
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed():
    settings = get_settings()
    logger.info(f"Connecting to database at {settings.DATABASE_URL}")
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")

    # Insert Demo User
    SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    async with SessionLocal() as session:
        # Create Demo user
        demo_user = User(
            email="demo@satark.ai",
            username="demouser",
            password_hash=hash_password("demo123"),
            is_active=True
        )
        session.add(demo_user)
        await session.flush()
        
        # Add sample scan history
        scan1 = Scan(
            id=uuid.uuid4(),
            user_id=demo_user.id,
            input_type=ScanInputType.message,
            raw_input="Your SBI account has been suspended. Verify now: http://sbi-secure-login.xyz",
            language="en",
            verdict=Verdict.PHISHING,
            risk_score=94.5,
            confidence=0.98,
            model_version="v1.0",
            shap_features=[{"feature": "suspended", "value": 1.2}, {"feature": "verify", "value": 0.8}],
            explanation="This message is a classic phishing scam. It creates a false sense of urgency by claiming your account is suspended and provides a suspicious link. Do not click the link or provide any personal information.",
            url_analysis={"url": "http://sbi-secure-login.xyz", "score": 1.0, "is_suspicious_tld": True}
        )
        
        scan2 = Scan(
            id=uuid.uuid4(),
            user_id=demo_user.id,
            input_type=ScanInputType.message,
            raw_input="IRCTC: Booking confirmed. PNR 4512387690, Train 12301, 20-Jun.",
            language="en",
            verdict=Verdict.SAFE,
            risk_score=5.2,
            confidence=0.99,
            model_version="v1.0",
            shap_features=[{"feature": "booking", "value": -0.5}, {"feature": "confirmed", "value": -0.6}],
            explanation="This message appears safe. It is a standard transactional SMS from IRCTC confirming a train ticket booking. No phishing indicators were detected.",
            url_analysis=None
        )
        
        session.add_all([scan1, scan2])
        await session.commit()
        logger.info("Database seeded successfully with demo user and sample scans.")

if __name__ == "__main__":
    asyncio.run(seed())
