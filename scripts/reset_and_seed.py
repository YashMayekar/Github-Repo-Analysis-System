import sys
import os

# Add parent directory to path to find 'app' module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from sqlmodel import Session, SQLModel
from app.db.session import engine
from app.models.db_models import CollectionRun, TeamScore, TeamAnalytics, Commit, FileChange, Team, EventConfig

# Define the database file path relative to this script
# script is in /scripts, db is in /data
DB_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'commit_collector.db')
EXCEL_FILE = os.path.join(os.path.dirname(__file__), '..', 'sample_teams.xlsx')

def reset_and_seed():
    print("--- Starting Database Reset ---")

    # 1. Delete DB file if exists to be 100% sure
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print(f"Deleted existing database: {DB_FILE}")
        except PermissionError:
            print(f"Error: Could not delete {DB_FILE}. Is it open?")
            return

    # 2. Create Tables
    print("Creating tables...")
    SQLModel.metadata.create_all(engine)
    
    # 3. Read Excel
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: {EXCEL_FILE} not found! Please create it first.")
        return

    try:
        df = pd.read_excel(EXCEL_FILE)
        print(f"Found {len(df)} teams in {EXCEL_FILE}")
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    with Session(engine) as session:
        # 4. Create Initial Run
        run = CollectionRun(description="Excel Import", status="completed", total_commits=0)
        session.add(run)
        session.commit()
        session.refresh(run)
        print(f"Created Run ID: {run.id}")
        
        # 5. Create Zero-Data for Teams from Excel
        for _, row in df.iterrows():
            team_name = row.get("teamname", "Unknown Team")
            # Cleaning name
            if pd.isna(team_name): continue
            team_name = str(team_name).strip()

            print(f"Seeding team: {team_name}")
            
            # # TeamScore (All 0s)
            # ts = TeamScore(
            #     run_id=run.id,
            #     team_name=team_name,
            #     productivity_score=0.0,
            #     commit_count=0,
            #     additions=0,
            #     deletions=0,
            #     churn_rate=0.0,
            #     is_finalized=False
            # )
            # session.add(ts)
            
            # Create Team Record for Background Monitoring
            repo_url = row.get("team_github_repo", "")
            if not pd.isna(repo_url) and repo_url:
                t = Team(name=team_name, repo_url=str(repo_url).strip(), branch="main")
                session.merge(t) # merge to avoid duplicates if any
            
            # session.flush() # Get ID
            
            # # TeamAnalytics (All Empty/Zeros)
            # analytics = TeamAnalytics(
            #     team_score_id=ts.id,
            #     hourly_commits=[0]*24,
            #     hourly_volume=[0]*24,
            #     top_files=[],
            #     top_folders=[],
            #     file_types=[]
            # )
            # session.add(analytics)
            
        session.commit()
        print("Database reset and seeded successfully from Excel.")

if __name__ == "__main__":
    reset_and_seed()
