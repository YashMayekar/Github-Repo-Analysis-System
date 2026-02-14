from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime, timedelta
from app.services.collector import collector_service
from app.services.ai_analysis import AIAnalysisService
from app.models.api_models import RunResponse
from sqlmodel import Session, select
from app.db.session import engine
from app.models.db_models import CollectionRun, TeamScore, Commit, Team, EventConfig

router = APIRouter()
ai_service = AIAnalysisService()

CLOCK_SKEW_BUFFER = timedelta(minutes=5)

def _get_active_event(session: Session):
    """Get the currently active event, or None."""
    return session.exec(
        select(EventConfig).where(EventConfig.is_active == True).order_by(EventConfig.id.desc())
    ).first()

def _get_since_iso(event) -> str:
    """Get the since ISO string with a clock-skew buffer."""
    buffered = event.event_start_time - CLOCK_SKEW_BUFFER
    return buffered.isoformat() + "Z"

@router.post("/start-event")
async def start_event():
    """Start a new hackathon event. Begins tracking commits from NOW."""
    with Session(engine) as session:
        # Deactivate any previous events
        old_events = session.exec(select(EventConfig).where(EventConfig.is_active == True)).all()
        for e in old_events:
            e.is_active = False
            session.add(e)
        
        # Create new event
        event = EventConfig(event_start_time=datetime.utcnow(), is_active=True)
        session.add(event)
        session.commit()
        session.refresh(event)
        
        return {
            "event_start_time": event.event_start_time.isoformat(),
            "is_active": True,
            "message": "Event started! Tracking commits from now."
        }

@router.get("/event-status")
def get_event_status():
    """Get the current event status."""
    with Session(engine) as session:
        event = _get_active_event(session)
        if not event:
            return {"is_active": False, "event_start_time": None, "elapsed_seconds": 0}
        
        elapsed = (datetime.utcnow() - event.event_start_time).total_seconds()
        
        return {
            "is_active": True,
            "event_start_time": event.event_start_time.isoformat(),
            "event_end_time": None,
            "elapsed_seconds": int(elapsed)
        }

@router.post("/refresh", response_model=RunResponse)
async def refresh_all_teams():
    """Trigger a manual refresh of all tracked teams."""
    with Session(engine) as session:
        event = _get_active_event(session)
        if not event:
            raise HTTPException(status_code=400, detail="No active event. Please start an event first.")
        
        since_iso = _get_since_iso(event)
        
        teams = session.exec(select(Team)).all()
        if not teams:
            raise HTTPException(status_code=404, detail="No tracked teams found. Run reset_and_seed.py first.")
            
        repos = []
        for t in teams:
            repos.append({
                "url": t.repo_url,
                "branch": t.branch,
                "team": t.name
            })
            
    if not repos:
        raise HTTPException(status_code=400, detail="No valid repositories to refresh.")

    run_id = await collector_service.start_collection_run(repos, description="Manual Refresh", since=since_iso)
    
    with Session(engine) as session:
        run = session.get(CollectionRun, run_id)
        return RunResponse(
            id=run.id,
            status=run.status,
            total_commits=run.total_commits,
            timestamp=run.timestamp
        )

@router.post("/end-event")
async def end_event():
    with Session(engine) as session:
        event = _get_active_event(session)
        if not event:
            raise HTTPException(status_code=400, detail="No active event to end.")

        teams = session.exec(select(Team)).all()
        if not teams:
            raise HTTPException(status_code=404, detail="No teams found.")

        finalized_teams = []
        skipped_teams = []

        for team in teams:
            latest_score = session.exec(
                select(TeamScore)
                .where(TeamScore.team_name == team.name)
                .order_by(TeamScore.id.desc())
            ).first()

            # Skip if already finalized
            if latest_score and latest_score.is_finalized:
                skipped_teams.append(team.name)
                continue

            commits = session.exec(
                select(Commit).where(Commit.team_name == team.name)
            ).all()

            if not commits:
                continue  # Skip teams with no commits

            summaries = [c.ai_explanation for c in commits if c.ai_explanation]
            scores = [c.ai_score for c in commits if c.ai_score]

            final_review = await ai_service.generate_final_review(
                team.name, summaries, scores
            )

            if latest_score:
                latest_score.final_review = final_review
                latest_score.is_finalized = True
                session.add(latest_score)
                finalized_teams.append(team.name)

        # Deactivate the event
        event.is_active = False
        event.event_end_time = datetime.utcnow()
        session.add(event)
        session.commit()


        return {
            "is_active": False,
            "event_end_time": event.event_end_time.isoformat(),
            "finalized_teams": finalized_teams,
            "skipped_teams": skipped_teams,
            "message": "Event ended. Team reviews finalized where applicable."
        }


@router.post("/finalize-team/{team_name}")
async def finalize_team_review(team_name: str):
    with Session(engine) as session:
        commits = session.exec(select(Commit).where(Commit.team_name == team_name)).all()
        if not commits:
            raise HTTPException(status_code=404, detail="No commits found for team")
            
        summaries = [c.ai_explanation for c in commits if c.ai_explanation]
        scores = [c.ai_score for c in commits if c.ai_score]
        
        final_review = await ai_service.generate_final_review(team_name, summaries, scores)
        
        statement = select(TeamScore).where(TeamScore.team_name == team_name).order_by(TeamScore.id.desc())
        latest_score = session.exec(statement).first()
        
        if latest_score:
            latest_score.final_review = final_review
            latest_score.is_finalized = True
            session.add(latest_score)
            session.commit()
            
        return {
            "team": team_name,
            "final_review": final_review,
            "status": "finalized"
        }
