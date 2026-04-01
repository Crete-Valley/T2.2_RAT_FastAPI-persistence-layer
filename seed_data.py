import asyncio

from db import AsyncSessionLocal, RatAssessment


async def seed():
    async with AsyncSessionLocal() as session:
        existing = await session.get(RatAssessment, 1)

        if not existing:
            session.add(RatAssessment(id=1, initiative_id=9999))
            await session.commit()
            print("Created placeholder RatAssessment with id=1")
        else:
            print("RatAssessment with id=1 already exists")


if __name__ == "__main__":
    asyncio.run(seed())