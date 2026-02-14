import asyncio
import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.db.session import engine
from app.models.db_models import Team, EventConfig
from app.services.collector import collector_service

logger = logging.getLogger(__name__)

CLOCK_SKEW_BUFFER = timedelta(minutes=5)

async def refresh_all_teams():
    """Logic to refresh all teams, only if event is active."""
    try:
        with Session(engine) as session:
            event = session.exec(
                select(EventConfig).where(EventConfig.is_active == True).order_by(EventConfig.id.desc())
            ).first()
            
            if not event:
                return  # No active event, skip
            
            buffered = event.event_start_time - CLOCK_SKEW_BUFFER
            since_iso = buffered.isoformat() + "Z"
            
            teams = session.exec(select(Team)).all()
            if not teams:
                return

            repos = []
            for t in teams:
                repos.append({
                    "url": t.repo_url,
                    "branch": t.branch,
                    "team": t.name
                })
        
        if repos:
            logger.info(f"Background Refresh: Scanning {len(repos)} teams (since {since_iso})...")
            await collector_service.start_collection_run(repos, description="Auto-Refresh", since=since_iso)
            
    except Exception as e:
        logger.error(f"Background Refresh Failed: {e}")

async def start_background_monitor():
    """Runs the refresh logic every 60 seconds."""
    logger.info("Starting Background Repository Monitor...")
    while True:
        await asyncio.sleep(60)
        await refresh_all_teams()
