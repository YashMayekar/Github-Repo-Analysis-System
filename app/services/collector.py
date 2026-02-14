import logging
import asyncio
import os
from collections import defaultdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.db.session import engine
from app.models.db_models import CollectionRun, Commit, TeamScore, FileChange, CollectionSummary
from src.github_client import GitHubAPIClient
from src.commit_processor import CommitProcessor
from src.team_mapper import TeamMapper
from app.core.config import settings
from app.services.queue_manager import queue_manager

logger = logging.getLogger(__name__)

class TeamMetrics:
    def __init__(self):
        self.commits: int = 0
        self.additions: int = 0
        self.deletions: int = 0
        self.hourly_commits: List[int] = [0] * 24
        self.hourly_volume: List[int] = [0] * 24
        self.file_changes: Dict[str, int] = defaultdict(int)
        self.folder_changes: Dict[str, int] = defaultdict(int)
        self.file_types: Dict[str, int] = defaultdict(int)

class CollectorService:
    def __init__(self):
        self.github_client = GitHubAPIClient(token=settings.GITHUB_TOKEN)
        self.team_mapper = TeamMapper({}) 
        self.processor = CommitProcessor(self.team_mapper)

    async def start_collection_run(self, repos: List[Dict[str, Any]], description: str, since: str = None) -> int:
        with Session(engine) as session:
            run = CollectionRun(description=description, status="running")
            session.add(run)
            session.commit()
            session.refresh(run)
            
            total_commits = 0
            all_commits_ids = []
            
            try:
                for repo_config in repos:
                    url = repo_config['url']
                    branch = repo_config.get('branch', 'main')
                    team_name = repo_config.get('team', 'Unknown')
                    
                    parts = url.strip("/").split("/")
                    owner, repo_name = parts[-2], parts[-1]
                    
                    raw_commits = self.github_client.get_commits(owner, repo_name, branch=branch, per_page=100, since=since)
                    
                    for rc in raw_commits:
                        # Skip if commit already exists in DB
                        existing = session.exec(select(Commit).where(Commit.sha == rc['sha'])).first()
                        if existing:
                            continue
                        
                        detailed = self.github_client.get_commit_details(owner, repo_name, rc['sha'])
                        processed = self.processor.process_commit(rc, owner, repo_name, url, branch, detailed_data=detailed)
                        
                        db_commit = Commit(
                            run_id=run.id,
                            sha=processed.commit_sha,
                            message=processed.commit_message,
                            author_name=processed.author_name,
                            team_name=team_name,
                            date=processed.commit_date,
                            url=processed.commit_url
                        )
                        session.add(db_commit)
                        session.commit()
                        session.refresh(db_commit)
                        
                        for fc in processed.file_changes:
                            db_fc = FileChange(
                                commit_id=db_commit.id,
                                filename=fc.filename,
                                status=fc.status,
                                additions=fc.additions,
                                deletions=fc.deletions,
                                patch=fc.patch
                            )
                            session.add(db_fc)
                        
                        all_commits_ids.append(db_commit.id)
                        total_commits += 1
                        
                run.status = "completed"
                run.total_commits = total_commits
                session.add(run)
                session.commit()
                
                await queue_manager.add_commits(all_commits_ids)
                
                self._calculate_team_scores(session, run.id)
                
                return run.id
                
            except Exception as e:
                logger.error(f"Collection Run Failed: {e}")
                run.status = "failed"
                session.add(run)
                session.commit()
                return run.id

    def _calculate_team_scores(self, session: Session, run_id: int):
        from app.models.db_models import TeamAnalytics, EventConfig

        # Get event start time for relative hour calculation
        event = session.exec(
            select(EventConfig).where(EventConfig.is_active == True).order_by(EventConfig.id.desc())
        ).first()
        event_start = event.event_start_time if event else None

        # Get all unique team names from this run
        run_commits = session.exec(select(Commit).where(Commit.run_id == run_id)).all()
        team_names = set(c.team_name for c in run_commits)
        
        # For each team, aggregate ALL their commits (across all runs) for full analytics
        all_team_commits = {}
        for tn in team_names:
            all_team_commits[tn] = session.exec(select(Commit).where(Commit.team_name == tn)).all()
        
        team_data: Dict[str, TeamMetrics] = defaultdict(TeamMetrics)

        for team_name, commits in all_team_commits.items():
            for c in commits:
                metrics = team_data[c.team_name]
                metrics.commits += 1
                
                # Calculate relative hour from event start
                if event_start and c.date:
                    delta_seconds = (c.date - event_start).total_seconds()
                    relative_hour = max(0, int(delta_seconds / 3600))
                    relative_hour = min(relative_hour, 23)  # Cap at 23
                else:
                    relative_hour = 0
                
                metrics.hourly_commits[relative_hour] += 1
                
                fchanges = session.exec(select(FileChange).where(FileChange.commit_id == c.id)).all()
                adds = sum(fc.additions for fc in fchanges)
                dels = sum(fc.deletions for fc in fchanges)
                
                metrics.additions += adds
                metrics.deletions += dels
                metrics.hourly_volume[relative_hour] += adds
                
                for fc in fchanges:
                    metrics.file_changes[fc.filename] += fc.additions + fc.deletions
                    
                    folder = os.path.dirname(fc.filename)
                    if not folder: folder = "/"
                    metrics.folder_changes[folder] += fc.additions + fc.deletions
                    
                    ext = os.path.splitext(fc.filename)[1] or "no_ext"
                    metrics.file_types[ext] += fc.additions + fc.deletions

        for team, stats in team_data.items():
            score = (stats.commits * 1.0) + (stats.additions * 0.1)
            churn = stats.deletions / stats.additions if stats.additions > 0 else 0.0
            
            ts = TeamScore(
                run_id=run_id,
                team_name=team,
                productivity_score=round(score, 2),
                commit_count=stats.commits,
                additions=stats.additions,
                deletions=stats.deletions,
                churn_rate=round(churn, 2)
            )
            session.add(ts)
            session.flush() 
            
            top_files = [{"name": k, "value": v} for k, v in sorted(stats.file_changes.items(), key=lambda x: x[1], reverse=True)[:5]]
            top_folders = [{"name": k, "value": v} for k, v in sorted(stats.folder_changes.items(), key=lambda x: x[1], reverse=True)[:5]]
            file_types = [{"name": k, "value": v} for k, v in sorted(stats.file_types.items(), key=lambda x: x[1], reverse=True)]
            
            analytics = TeamAnalytics(
                team_score_id=ts.id,
                hourly_commits=stats.hourly_commits,
                hourly_volume=stats.hourly_volume,
                top_files=top_files,
                top_folders=top_folders,
                file_types=file_types
            )
            session.add(analytics)
        
        session.commit()

collector_service = CollectorService()
