import asyncio
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

async def test():
    engine = create_async_engine('postgresql+asyncpg://postgres:Dhruv%402004@localhost:5432/satark_ai')
    async with engine.connect() as conn:
        result = await conn.execute(sqlalchemy.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        tables = result.fetchall()
        print('Tables:', [t[0] for t in tables])

if __name__ == '__main__':
    asyncio.run(test())
