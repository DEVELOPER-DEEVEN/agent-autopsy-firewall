import hashlib
import os
import datetime
from typing import Optional, List

from sqlmodel import Field, SQLModel, Session, create_engine, select
from pydantic import BaseModel

DEFAULT_DB_PATH = os.path.expanduser("~/.autopsy/autopsy.db")


class Episode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    signature: str
    task: str
    outcome: str  # "success" | "failure"
    summary: str
    trace_path: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class EpisodeMatch(BaseModel):
    episode: Episode
    similarity: float


def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def get_engine(db_path: str = DEFAULT_DB_PATH):
    _ensure_dir(db_path)
    return create_engine(f"sqlite:///{db_path}")


def init_db(db_path: str = DEFAULT_DB_PATH):
    engine = get_engine(db_path)
    SQLModel.metadata.create_all(engine)
    return engine


def hash_signature(task: str, plan: str) -> str:
    h = hashlib.sha256()
    h.update(task.encode())
    h.update(plan.encode())
    return h.hexdigest()


def record_episode(task: str, plan: str, outcome: str, summary: str, trace_path: str, db_path: str = DEFAULT_DB_PATH) -> Episode:
    engine = init_db(db_path)
    signature = hash_signature(task, plan)
    ep = Episode(signature=signature, task=task, outcome=outcome, summary=summary, trace_path=trace_path)
    with Session(engine) as session:
        session.add(ep)
        session.commit()
        session.refresh(ep)
        return ep


def find_failures_like(task: str, plan: str, db_path: str = DEFAULT_DB_PATH) -> List[EpisodeMatch]:
    engine = init_db(db_path)
    signature = hash_signature(task, plan)
    with Session(engine) as session:
        statement = select(Episode).where(Episode.signature == signature, Episode.outcome == "failure")
        results = session.exec(statement).all()
        return [EpisodeMatch(episode=r, similarity=1.0) for r in results]
