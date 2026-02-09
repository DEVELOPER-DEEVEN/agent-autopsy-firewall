import hashlib
import os
import datetime
from typing import Optional, List
from difflib import SequenceMatcher

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
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


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


def plan_similarity(a: str, b: str) -> float:
    """Cheap heuristic similarity for plans (0-1)."""
    return SequenceMatcher(None, a, b).ratio()


def record_episode(task: str, plan: str, outcome: str, summary: str, trace_path: str, db_path: str = DEFAULT_DB_PATH) -> Episode:
    engine = init_db(db_path)
    signature = hash_signature(task, plan)
    ep = Episode(signature=signature, task=task, outcome=outcome, summary=summary, trace_path=trace_path)
    with Session(engine) as session:
        session.add(ep)
        session.commit()
        session.refresh(ep)
        return ep


def find_failures_like(task: str, plan: str, db_path: str = DEFAULT_DB_PATH, min_similarity: float = 0.8) -> List[EpisodeMatch]:
    engine = init_db(db_path)
    signature = hash_signature(task, plan)
    with Session(engine) as session:
        # Exact signature match first
        statement = select(Episode).where(Episode.signature == signature, Episode.outcome == "failure")
        exact = session.exec(statement).all()

        # Fuzzy match on task+plan
        statement_all = select(Episode).where(Episode.outcome == "failure")
        all_eps = session.exec(statement_all).all()
        fuzzy = []
        for ep in all_eps:
            sim = plan_similarity(ep.plan if hasattr(ep, "plan") else ep.summary, plan)
            if sim >= min_similarity:
                fuzzy.append(EpisodeMatch(episode=ep, similarity=sim))

        matches = [EpisodeMatch(episode=r, similarity=1.0) for r in exact]
        matches.extend(fuzzy)
        # Deduplicate by id keeping highest similarity
        best = {}
        for m in matches:
            if m.episode.id not in best or m.similarity > best[m.episode.id].similarity:
                best[m.episode.id] = m
        return sorted(best.values(), key=lambda m: m.similarity, reverse=True)
