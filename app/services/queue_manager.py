import asyncio
import logging
from typing import List
from sqlmodel import Session
from app.db.session import engine
from app.models.db_models import Commit
from app.services.ai_analysis import AIAnalysisService

logger = logging.getLogger(__name__)

class QueueManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QueueManager, cls).__new__(cls)
            cls._instance.queue = asyncio.Queue()
            cls._instance.ai_service = AIAnalysisService()
            cls._instance.is_running = False
        return cls._instance

    async def add_commits(self, commit_ids: List[int]):
        for cid in commit_ids:
            await self.queue.put(cid)
        
        if not self.is_running:
            asyncio.create_task(self.process_queue())

    async def process_queue(self):
        self.is_running = True
        logger.info("Starting background commit processing queue")
        
        with Session(engine) as session:
            while not self.queue.empty():
                commit_id = await self.queue.get()
                try:
                    commit = session.get(Commit, commit_id)
                    if not commit:
                        continue
                        
                    diffs = "\n".join([
                        f"File: {fc.filename} ({fc.status})\n{fc.patch or ''}"
                        for fc in commit.file_changes
                    ])
                    
                    analysis = await self.ai_service.analyze_commit(commit.message, diffs)
                    
                    commit.ai_score = analysis.get("score", 10)
                    commit.is_ai_generated = analysis.get("is_ai", False)
                    commit.ai_explanation = analysis.get("explanation", "")
                    
                    session.add(commit)
                    session.commit()
                    
                    logger.info(f"Analyzed commit {commit.sha}: {commit.ai_score}/20")
                    
                except Exception as e:
                    logger.error(f"Error processing commit {commit_id}: {e}")
                finally:
                    self.queue.task_done()
        
        self.is_running = False
        logger.info("Queue processing complete")

queue_manager = QueueManager()
