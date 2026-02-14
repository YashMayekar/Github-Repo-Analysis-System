from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.db_models import CollectionRun, TeamScore, Commit, FileChange, Team
from app.models.api_models import TeamScoreResponse, CommitResponse, TeamAnalyticsResponse

router = APIRouter()

@router.get("/teams", response_model=List[TeamScoreResponse])
def get_team_history(session: Session = Depends(get_session)):
    """
    Retrieve all teams with their current scores.
    Teams with no commits will return zeroed scores.
    """

    # 1️⃣ Get active hackathon run
    run = session.exec(
        select(CollectionRun)
        .where(CollectionRun.status == "running")
    ).first()

    # 2️⃣ Fetch all teams
    teams = session.exec(select(Team)).all()

    # 3️⃣ Fetch scores ONLY for active run
    scores = []
    if run:
        scores = session.exec(
            select(TeamScore)
            .where(TeamScore.run_id == run.id)
        ).all()

    score_map = {s.team_name: s for s in scores}

    # 4️⃣ Merge (LEFT JOIN behavior)
    response: List[TeamScoreResponse] = []

    for team in teams:
        ts = score_map.get(team.name)

        response.append(
            TeamScoreResponse(
                team_name=team.name,
                commit_count=ts.commit_count if ts else 0,
                additions=ts.additions if ts else 0,
                deletions=ts.deletions if ts else 0,
                churn_rate=ts.churn_rate if ts else 0.0,
                productivity_score=ts.productivity_score if ts else 0.0,
                is_finalized=ts.is_finalized if ts else False,
            )
        )

    return response

@router.get("/summary")
def get_collection_history(session: Session = Depends(get_session)):
    """
    Retrieve one-line summaries of past runs.
    """
    runs = session.exec(select(CollectionRun).order_by(CollectionRun.timestamp.desc())).all()
    return [{"id": r.id, "date": r.timestamp, "desc": r.description, "status": r.status} for r in runs]

@router.get("/commits/{run_id}", response_model=List[CommitResponse])
def get_run_commits(run_id: int, session: Session = Depends(get_session)):
    """
    Retrieve commits for a specific run.
    """
    commits = session.exec(select(Commit).where(Commit.run_id == run_id)).all()
    return commits

@router.get("/diffs/{commit_id}")
def get_commit_diffs(commit_id: int, session: Session = Depends(get_session)):
    changes = session.exec(select(FileChange).where(FileChange.commit_id == commit_id)).all()
    return changes

@router.get("/analytics/{team_name}", response_model=List[TeamAnalyticsResponse])
def get_team_analytics(team_name: str, session: Session = Depends(get_session)):
    from app.models.db_models import TeamAnalytics, Commit
    from app.models.api_models import CommitSummary
    
    # Get latest score to find analytics
    statement = select(TeamScore).where(TeamScore.team_name == team_name).order_by(TeamScore.id.desc())
    latest_score = session.exec(statement).first()
    
    if not latest_score or not latest_score.analytics:
        # Return empty structure if no data yet
        return [TeamAnalyticsResponse(
            team_name=team_name,
            hourly_commits=[0]*24,
            hourly_volume=[0]*24,
            top_files=[],
            top_folders=[],
            file_types=[],
            recent_commits=[],
            final_review=None
        )]

    # Fetch recent commits
    commits = session.exec(
        select(Commit)
        .where(Commit.run_id == latest_score.run_id, Commit.team_name == team_name)
        .order_by(Commit.date.desc())
        .limit(20)
    ).all()

    recent_commits = [
        CommitSummary(
            message=c.message,
            author_name=c.author_name,
            score=c.ai_score or 0,
            summary=c.ai_explanation or "No summary available",
            url=c.url,
            date=c.date
        ) for c in commits
    ]
        
    return [TeamAnalyticsResponse(
        team_name=team_name,
        commit_count=latest_score.commit_count,
        additions=latest_score.additions,
        deletions=latest_score.deletions,
        churn_rate=latest_score.churn_rate,
        productivity_score=latest_score.productivity_score,
        hourly_commits=latest_score.analytics.hourly_commits,
        hourly_volume=latest_score.analytics.hourly_volume,
        top_contributors=latest_score.analytics.top_contributors,
        top_files=latest_score.analytics.top_files,
        top_folders=latest_score.analytics.top_folders,
        file_types=latest_score.analytics.file_types,
        recent_commits=recent_commits,
        final_review=latest_score.final_review
    )]
