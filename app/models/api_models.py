from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class RunCreate(BaseModel):
    description: str
    repos: List[dict] # {url: str, branch: str, team: str}

class RunResponse(BaseModel):
    id: int
    status: str
    total_commits: int
    timestamp: datetime

class TeamScoreResponse(BaseModel):
    team_name: str
    productivity_score: float
    commit_count: int
    additions: int
    deletions: int
    churn_rate: float
    is_finalized: bool = False
    final_review: Optional[str] = None

from datetime import datetime

class CommitSummary(BaseModel):
    message: str
    author_name: str
    score: int
    summary: str
    url: str
    date: datetime

class TeamAnalyticsResponse(BaseModel):
    team_name: str
    commit_count: int
    additions: int
    deletions: int
    churn_rate: float
    productivity_score: float
    hourly_commits: List[int]
    hourly_volume: List[int]
    top_contributors: List[dict]
    top_files: List[dict]
    top_folders: List[dict]
    file_types: List[dict]
    recent_commits: List[CommitSummary] = []
    final_review: Optional[str] = None

class CommitResponse(BaseModel):
    sha: str
    message: str
    author_name: str
    date: datetime
    ai_score: Optional[int]
    ai_explanation: Optional[str]
    is_ai_generated: bool
