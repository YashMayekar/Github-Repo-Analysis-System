from datetime import datetime
from typing import Optional, List, Dict
from sqlmodel import Field, SQLModel, Relationship, JSON

class EventConfig(SQLModel, table=True):
    __tablename__ = "event_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    event_start_time: datetime
    event_end_time: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Team(SQLModel, table=True):
    __tablename__ = "teams"
    name: str = Field(primary_key=True)
    repo_url: str
    branch: str = "main"
    created_at: datetime = Field(default_factory=datetime.now)

class CollectionRun(SQLModel, table=True):
    __tablename__ = "collection_runs"
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    total_commits: int = 0
    description: Optional[str] = None
    status: str = "pending"
    ai_summary: Optional[str] = None
    final_review: Optional[str] = None
    
    commits: List["Commit"] = Relationship(back_populates="run")
    team_scores: List["TeamScore"] = Relationship(back_populates="run")
    summaries: List["CollectionSummary"] = Relationship(back_populates="run")

class TeamAnalytics(SQLModel, table=True):
    __tablename__ = "team_analytics"
    id: Optional[int] = Field(default=None, primary_key=True)
    team_score_id: int = Field(foreign_key="team_scores.id")
    
    hourly_commits: List[int] = Field(sa_type=JSON, default=[0]*24)
    hourly_volume: List[int] = Field(sa_type=JSON, default=[0]*24)
    top_files: List[Dict] = Field(sa_type=JSON, default=[])
    top_folders: List[Dict] = Field(sa_type=JSON, default=[])
    file_types: List[Dict] = Field(sa_type=JSON, default=[])
    top_contributors: List[Dict] = Field(sa_type=JSON, default=[])

    team_score: "TeamScore" = Relationship(back_populates="analytics")

class TeamScore(SQLModel, table=True):
    __tablename__ = "team_scores"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collection_runs.id")
    team_name: str
    productivity_score: float = 0.0
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0
    churn_rate: float = 0.0
    
    is_finalized: bool = False
    final_review: Optional[str] = None
    
    run: CollectionRun = Relationship(back_populates="team_scores")
    analytics: Optional[TeamAnalytics] = Relationship(back_populates="team_score")

class CollectionSummary(SQLModel, table=True):
    __tablename__ = "collection_summaries"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collection_runs.id")
    summary_text: str
    top_contributor: Optional[str] = None
    repositories_scanned: int = 0
    
    run: CollectionRun = Relationship(back_populates="summaries")

class Commit(SQLModel, table=True):
    __tablename__ = "commits"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collection_runs.id")
    sha: str = Field(index=True)
    message: str
    author_name: str
    team_name: str
    date: datetime
    url: str
    
    ai_score: Optional[int] = None
    ai_explanation: Optional[str] = None
    is_ai_generated: bool = False
    
    run: CollectionRun = Relationship(back_populates="commits")
    file_changes: List["FileChange"] = Relationship(back_populates="commit")

class FileChange(SQLModel, table=True):
    __tablename__ = "file_changes"
    id: Optional[int] = Field(default=None, primary_key=True)
    commit_id: int = Field(foreign_key="commits.id")
    filename: str
    status: str
    additions: int
    deletions: int
    patch: Optional[str] = None
    
    commit: Commit = Relationship(back_populates="file_changes")
