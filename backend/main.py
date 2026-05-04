import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.future import select

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://myuser:mypassword@localhost:5432/balance_game")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True, index=True, nullable=False)
    votes_a = Column(Integer, default=0)
    votes_b = Column(Integer, default=0)

# Create tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class VoteRequest(BaseModel):
    choice: str  # 'A' or 'B'

@app.get("/api/votes/{date}")
async def get_votes(date: str):
    async with async_session() as session:
        result = await session.execute(select(Vote).where(Vote.date == date))
        vote = result.scalars().first()
        if vote:
            return {"date": date, "votesA": vote.votes_a, "votesB": vote.votes_b}
        else:
            return {"date": date, "votesA": 0, "votesB": 0}

@app.post("/api/votes/{date}")
async def cast_vote(date: str, request: VoteRequest):
    if request.choice not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Invalid choice")

    async with async_session() as session:
        # Check if row exists
        result = await session.execute(select(Vote).where(Vote.date == date))
        vote = result.scalars().first()
        
        if not vote:
            # Create new row
            new_vote = Vote(date=date, votes_a=0, votes_b=0)
            if request.choice == 'A':
                new_vote.votes_a = 1
            else:
                new_vote.votes_b = 1
            session.add(new_vote)
        else:
            # Update existing row
            if request.choice == 'A':
                vote.votes_a += 1
            else:
                vote.votes_b += 1
            
        await session.commit()
        
        return {"message": "Vote cast successfully"}
