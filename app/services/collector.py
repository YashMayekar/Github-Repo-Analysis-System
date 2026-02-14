import logging
import os
from collections import defaultdict
from typing import List, Dict, Any
from datetime import datetime
from sqlmodel import Session, select

from app.db.session import engine
from app.models.db_models import (
    CollectionRun,
    Commit,
    TeamScore,
    FileChange,
)
from src.github_client import GitHubAPIClient
from src.commit_processor import CommitProcessor
from src.team_mapper import TeamMapper
from app.core.config import settings
from app.services.queue_manager import queue_manager

logger = logging.getLogger(__name__)


class CollectorService:
    def __init__(self):
        self.github_client = GitHubAPIClient(token=settings.GITHUB_TOKEN)
        self.team_mapper = TeamMapper({})
        self.processor = CommitProcessor(self.team_mapper)

    async def start_collection_run(
        self,
        repos: List[Dict[str, Any]],
        description: str,
        since: str = None
    ) -> int:
        """
        ONE run for the entire hackathon.
        This function updates it every minute.
        """

        with Session(engine) as session:

            # ✅ REUSE ACTIVE RUN
            run = session.exec(
                select(CollectionRun)
                .where(CollectionRun.status == "running")
            ).first()

            if not run:
                run = CollectionRun(
                    description=description,
                    status="running",
                )
                session.add(run)
                session.commit()
                session.refresh(run)

            new_commit_ids: List[int] = []

            try:
                for repo_config in repos:
                    url = repo_config["url"]
                    branch = repo_config.get("branch", "main")
                    team_name = repo_config.get("team", "Unknown")

                    parts = url.rstrip("/").split("/")
                    owner, repo_name = parts[-2], parts[-1]

                    raw_commits = self.github_client.get_commits(
                        owner,
                        repo_name,
                        branch=branch,
                        per_page=100,
                        since=since,
                    )

                    for rc in raw_commits:
                        # ✅ Global SHA dedupe
                        existing = session.exec(
                            select(Commit).where(Commit.sha == rc["sha"])
                        ).first()
                        if existing:
                            continue

                        detailed = self.github_client.get_commit_details(
                            owner, repo_name, rc["sha"]
                        )

                        processed = self.processor.process_commit(
                            rc,
                            owner,
                            repo_name,
                            url,
                            branch,
                            detailed_data=detailed,
                        )

                        db_commit = Commit(
                            run_id=run.id,
                            sha=processed.commit_sha,
                            message=processed.commit_message,
                            author_name=processed.author_name,
                            team_name=team_name,
                            date=processed.commit_date,
                            url=processed.commit_url,
                        )
                        session.add(db_commit)
                        session.flush()

                        for fc in processed.file_changes:
                            session.add(
                                FileChange(
                                    commit_id=db_commit.id,
                                    filename=fc.filename,
                                    status=fc.status,
                                    additions=fc.additions,
                                    deletions=fc.deletions,
                                    patch=fc.patch,
                                )
                            )

                        new_commit_ids.append(db_commit.id)

                run.total_commits += len(new_commit_ids)
                session.commit()

                if new_commit_ids:
                    await queue_manager.add_commits(new_commit_ids)

                # ✅ RECALCULATE CUMULATIVE SCORES
                self._calculate_team_scores(session, run.id)

                return run.id

            except Exception as e:
                logger.exception("Collection run failed")
                run.status = "failed"
                session.commit()
                return run.id

    def _calculate_team_scores(self, session: Session, run_id: int):
        from app.models.db_models import TeamAnalytics, EventConfig

        event = session.exec(
            select(EventConfig)
            .where(EventConfig.is_active == True)
            .order_by(EventConfig.id.desc())
        ).first()

        event_start = event.event_start_time if event else None

        # ✅ ALL COMMITS SO FAR (CUMULATIVE)
        commits = session.exec(
            select(Commit).where(Commit.run_id == run_id)
        ).all()

        team_commits: Dict[str, List[Commit]] = defaultdict(list)
        for c in commits:
            team_commits[c.team_name].append(c)

        for team, commits in team_commits.items():
            ts = session.exec(
                select(TeamScore)
                .where(TeamScore.run_id == run_id)
                .where(TeamScore.team_name == team)
            ).first()

            if not ts:
                ts = TeamScore(run_id=run_id, team_name=team)
                session.add(ts)
                session.flush()

            additions = 0
            deletions = 0
            hourly_commits = [0] * 24
            hourly_volume = [0] * 24
            contributors = defaultdict(int)

            file_changes = defaultdict(int)
            folder_changes = defaultdict(int)
            file_types = defaultdict(int)

            for c in commits:
                contributors[c.author_name] += 1

                hour = 0
                if event_start and c.date:
                    hour = min(
                        max(int((c.date - event_start).total_seconds() / 3600), 0),
                        23,
                    )

                hourly_commits[hour] += 1

                fcs = session.exec(
                    select(FileChange).where(FileChange.commit_id == c.id)
                ).all()

                for fc in fcs:
                    additions += fc.additions
                    deletions += fc.deletions
                    hourly_volume[hour] += fc.additions

                    file_changes[fc.filename] += fc.additions + fc.deletions
                    folder = os.path.dirname(fc.filename) or "/"
                    folder_changes[folder] += fc.additions + fc.deletions
                    ext = os.path.splitext(fc.filename)[1] or "no_ext"
                    file_types[ext] += fc.additions + fc.deletions

            ts.commit_count = len(commits)
            ts.additions = additions
            ts.deletions = deletions
            ts.churn_rate = round(
                deletions / additions if additions else 0.0, 2
            )
            ts.productivity_score = round(
                ts.commit_count + additions * 0.1, 2
            )

            analytics = session.exec(
                select(TeamAnalytics)
                .where(TeamAnalytics.team_score_id == ts.id)
            ).first()

            if not analytics:
                analytics = TeamAnalytics(team_score_id=ts.id)
                session.add(analytics)

            analytics.hourly_commits = hourly_commits
            analytics.hourly_volume = hourly_volume
            analytics.top_files = sorted(
                [{"name": k, "value": v} for k, v in file_changes.items()],
                key=lambda x: x["value"],
                reverse=True,
            )[:5]
            analytics.top_folders = sorted(
                [{"name": k, "value": v} for k, v in folder_changes.items()],
                key=lambda x: x["value"],
                reverse=True,
            )[:5]
            analytics.file_types = sorted(
                [{"name": k, "value": v} for k, v in file_types.items()],
                key=lambda x: x["value"],
                reverse=True,
            )
            analytics.top_contributors = sorted(
                [{"name": k, "commits": v} for k, v in contributors.items()],
                key=lambda x: x["commits"],
                reverse=True,
            )[:5]

        session.commit()

collector_service = CollectorService()
