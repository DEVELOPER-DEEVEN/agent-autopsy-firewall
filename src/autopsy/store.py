import hashlib
import os
import datetime
import math
import collections
import re
from typing import Optional, List, Dict, Union
from difflib import SequenceMatcher

from sqlmodel import Field, SQLModel, Session, create_engine, select
from pydantic import BaseModel

DEFAULT_DB_PATH = os.path.expanduser("~/.autopsy/autopsy.db")


class Episode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    signature: str
    task: str
    plan: str
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


def tokenize(text: str) -> List[str]:
    """Simple tokenizer for pure-python similarity."""
    return re.findall(r'\w+', text.lower())


def cosine_similarity_pure(text1: str, text2: str) -> float:
    """Compute cosine similarity between two strings using Bag of Words (Pure Python)."""
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    
    if not tokens1 or not tokens2:
        return 0.0
        
    count1 = collections.Counter(tokens1)
    count2 = collections.Counter(tokens2)
    
    terms = set(count1.keys()) | set(count2.keys())
    
    dot_product = sum(count1.get(t, 0) * count2.get(t, 0) for t in terms)
    mag1 = math.sqrt(sum(v**2 for v in count1.values()))
    mag2 = math.sqrt(sum(v**2 for v in count2.values()))
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
        
    return dot_product / (mag1 * mag2)


def plan_similarity(a: str, b: str, method: str = "fuzzy") -> float:
    """Compute similarity for plans using various methods."""
    if method == "exact":
        return 1.0 if a == b else 0.0
    elif method == "cosine":
        return cosine_similarity_pure(a, b)
    else:  # default fuzzy
        return SequenceMatcher(None, a, b).ratio()


def record_episode(task: str, plan: str, outcome: str, summary: str, trace_path: str, db_path: str = DEFAULT_DB_PATH) -> Episode:
    engine = init_db(db_path)
    signature = hash_signature(task, plan)
    ep = Episode(signature=signature, task=task, plan=plan, outcome=outcome, summary=summary, trace_path=trace_path)
    with Session(engine) as session:
        session.add(ep)
        session.commit()
        session.refresh(ep)
        return ep


def find_failures_like(task: str, plan: str, db_path: str = DEFAULT_DB_PATH, min_similarity: float = 0.8, method: str = "fuzzy") -> List[EpisodeMatch]:
    engine = init_db(db_path)
    signature = hash_signature(task, plan)
    
    with Session(engine) as session:
        # 1. Exact signature match check (Optimization)
        statement = select(Episode).where(Episode.signature == signature, Episode.outcome == "failure")
        exact_results = session.exec(statement).all()
        matches = [EpisodeMatch(episode=ep, similarity=1.0) for ep in exact_results]
        
        # 2. Heuristic check (Fuzzy/Cosine)
        if method != "exact":
            statement_all = select(Episode).where(Episode.outcome == "failure")
            all_eps = session.exec(statement_all).all()
            
            for ep in all_eps:
                # Skip if already found via exact match
                if any(m.episode.id == ep.id for m in matches):
                    continue
                    
                # Combine task and plan for a better semantic context
                ep_full = f"{ep.task} {ep.plan}"
                current_full = f"{task} {plan}"
                
                sim = plan_similarity(ep_full, current_full, method=method)
                if sim >= min_similarity:
                    matches.append(EpisodeMatch(episode=ep, similarity=sim))

        # Deduplicate and sort
        best = {}
        for m in matches:
            if m.episode.id not in best or m.similarity > best[m.episode.id].similarity:
                best[m.episode.id] = m
                
        return sorted(best.values(), key=lambda m: m.similarity, reverse=True)
