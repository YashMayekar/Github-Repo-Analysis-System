# GitHub Commit Collector & AI Analyzer

A real-time dashboard for tracking, analyzing, and scoring hackathon team performance based on their GitHub activity. It uses AI to rate code quality and provides detailed analytics.

## 🚀 Workflow

1.  **Setup**: Add team names and repository URLs to `sample_teams.xlsx`, then run `python scripts/reset_and_seed.py` to initialize the database.
2.  **Start Event**: Click the "Start Event" button in the dashboard. This records the event start time and begins tracking.
3.  **Continuous Monitoring**:
    -   **Background**: The server checks for new commits every **60 seconds** while an event is active.
    -   **Manual**: Use the "Refresh Data" button to trigger an immediate scan.
4.  **Data Processing**:
    -   Commits are fetched via GitHub API (filtered by event start time with a 5-minute clock-skew buffer).
    -   Duplicate commits are skipped by SHA to avoid re-processing.
    -   **Quantitative Analysis**: Lines added, deleted, file types, churn rate.
    -   **Qualitative Analysis (AI)**: A local LLM (Ollama/Mistral) analyzes every commit diff to assign a quality score (0-20) and detect "AI-generated" spam.
5.  **Visualization**: The frontend updates to show leaderboards, timelines (hourly from event start), and deep-dive analytics for each team.
6.  **Finalize**: Click "Finalize Event" to generate final AI performance reviews for each team and end the event.
7. **Important entry points**: `app\services\collector.py`, `app\api\v1\endpoints\collectors.py`
---

## ⏱️ Event Lifecycle

The system is built around an **Event** — a tracking window that starts when you press "Start Event" and ends when you "Finalize".

| Phase | What Happens |
| :--- | :--- |
| **Pre-Event** | Seed teams via `reset_and_seed.py`. Only "Start Event" button is visible. |
| **Active Event** | Timer counts up. Refresh & Finalize buttons appear. Background auto-refresh runs every 60s. |
| **Finalize** | AI generates a final review per team. Event is deactivated. |

- All analytics use **relative hours** from event start (Hr 1, Hr 2, ... Hr 24).
- The `since` filter uses `event_start_time - 5 minutes` to account for clock skew between your machine and GitHub.

---

## 📊 Scoring System

The system uses a hybrid scoring mechanism:

### 1. Productivity Score (Quantitative)
Calculated based on raw activity:
```python
Score = (Commit Count * 1.0) + (Lines Added * 0.1)
```
*Note: High churn (deletions/additions) is tracked but doesn't directly penalize the score yet.*

### 2. AI Quality Score (Qualitative)
Every commit is analyzed by an AI model (Mistral) with "Brutally Honest" criteria:

-   **0-5 (Critical)**: Buggy, broken logic, obvious placeholders, or nonsensical "vibecoding".
-   **6-12 (Average)**: Standard boilerplate, config updates, minor tweaks, or simple CRUD.
-   **13-17 (Good)**: Distinct logic improvement, good refactoring, clean implementation.
-   **18-20 (Exceptional)**: Complex algorithm optimization, highly efficient "10x" code.

---

## 📂 Database Structure (SQLite)

The system uses **SQLModel** (SQLAlchemy + Pydantic).

| Table | Description | Key Fields |
| :--- | :--- | :--- |
| **event_config** | Tracks event lifecycle | `id`, `event_start_time`, `is_active`, `created_at` |
| **teams** | Registry of tracked repos | `name` (PK), `repo_url`, `branch` |
| **collection_runs** | History of scan events | `id`, `timestamp`, `status`, `total_commits` |
| **commits** | Individual commit data | `sha`, `message`, `author`, `ai_score`, `is_ai_generated`, `ai_explanation` |
| **file_changes** | Diff details per file | `filename`, `additions`, `deletions`, `status` |
| **team_scores** | Aggregated team metrics | `productivity_score`, `churn_rate`, `commit_count` |
| **team_analytics** | Detailed JSON stats | `hourly_commits`, `hourly_volume`, `top_files` (JSON), `file_types` (JSON) |

---

## 🔌 API Endpoints

### Event Management
-   `POST /api/v1/collect/start-event`: Start a new event. Deactivates any previous events and records the current UTC time as event start.
-   `GET /api/v1/collect/event-status`: Get the active event status, including `is_active`, `event_start_time`, and `elapsed_seconds`.

### Collectors
-   `POST /api/v1/collect/refresh`: Trigger a manual refresh for all teams. Requires an active event. Uses `since` filter (event start - 5min buffer).
-   `POST /api/v1/collect/finalize/{team_name}`: Generate a final AI performance review for a team and deactivate the event.

### History & Analytics
-   `GET /api/v1/history/summary`: Get the main leaderboard list.
-   `GET /api/v1/history/teams`: Get all tracked teams with their latest scores.
-   `GET /api/v1/history/analytics/{team_name}`: Get deep-dive analytics (charts/graphs data).

---

## 🛠️ Setup & Usage

### Prerequisites
- Python 3.10+
- Node.js 18+
- GitHub Personal Access Token
- Ollama with Mistral model (for AI analysis)

### Installation

```bash
# Backend setup
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..
```

### Configuration

1. Set your GitHub token as an environment variable or in `.env`:
   ```
   GITHUB_TOKEN=ghp_your_token_here
   ```

2. Add teams to `sample_teams.xlsx`:

| teamname | team_github_repo |
| :--- | :--- |
| Team Alpha | https://github.com/user/project-alpha |
| Beta Coders | https://github.com/user/beta-backend |

### Running

```bash
# 1. Seed the database
.\venv\Scripts\python scripts/reset_and_seed.py

# 2. Start the backend
.\venv\Scripts\uvicorn app.main:app --reload

# 3. Start the frontend (in another terminal)
cd frontend
npm run dev
```

### Event Flow
1. Open `http://localhost:5173` in your browser.
2. Click **Start Event** to begin tracking.
3. Teams make commits to their repos.
4. Click **Refresh** (or wait for auto-refresh every 60s) to fetch new commits.
5. View analytics by clicking on a team in the leaderboard.
6. Click **Finalize Event** when done to generate AI reviews.

---

## 📝 Output Sample (Team Analytics JSON)

Response from `/api/v1/history/analytics/{team_name}`:
if finalized button hit then "final_review" = data, else "final_review" = None
```json
{
  "team_name": "XYZ",
  "commit_count": 7,
  "additions": 1344,
  "deletions": 1123,
  "churn_rate": 50.0,
  "productivity_score": 56.1,
  "hourly_commits": [5, 12, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  "hourly_volume": [150, 430, 120, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  "top_files": [
    {"name": "src/main.py", "value": 450},
    {"name": "readme.md", "value": 120},
    {"name": "config.json", "value": 85}
  ],
  "top_folders": [
    {"name": "src", "value": 515},
    {"name": "docs", "value": 120}
  ],
  "file_types": [
    {"name": ".py", "value": 555},
    {"name": ".md", "value": 120},
    {"name": ".json", "value": 85}
  ],
   "recent_commits": [
        {
            "message": "First commit",
            "author_name":"ABC",
            "score": 5,
            "summary": "Small adjustment of comment in a function",
            "url": "https://github.com/xys/webhacks/commit/3c4fe46dc06f11c1baae18c28a997d7970ab8ac2",
            "date": "2026-02-11T22:59:40"
        },
        {
            "message": "Second commit",
            "author_name":"ABC",
            "score": 5,
            "summary": "Small adjustment of comment in a function",
            "url": "https://github.com/xys/webhacks/commit/3c4fe46dc06f11c1baae18c28a997d7970ab8ac2",
            "date": "2026-02-11T22:59:40"
        }
    ],
    "final_review": "Team XYZ demonstrates a proficient understanding of code adjustments, with an average score of 13. This suggests a steady level of performance. While they have not shown extensive use of AI, their work indicates attention to detail and problem-solving skills. Continued focus on optimization and complexity management is recommended for further growth."
}
```


Response from `/api/v1/history/teams`
if finalized button hit then "final_review" = data, else "final_review" = None
```json
[
    {
        "team_name": "ABC",
        "commit_count": 0,
        "additions": 0,
        "deletions": 0,
        "churn_rate": 0.0,
        "productivity_score": 0.0,
        "is_finalized": false,
        "final_review": null
    },
    {
        "team_name": "XYZ",
        "commit_count": 0,
        "additions": 0,
        "deletions": 0,
        "churn_rate": 0.0,
        "productivity_score": 0.0,
        "is_finalized": false,
        "final_review": null
    },
    {
        "team_name": "XYZ",
        "commit_count": 12,
        "additions": 3234,
        "deletions": 1340,
        "churn_rate": 70.0,
        "productivity_score": 19.7,
        "is_finalized": true,
        "final_review": "Team 'XYZ' demonstrates a consistent level of performance, with an average score of 13. This places them within the \"Meets Expectations\" range. Notably, there are indicators suggesting an increased reliance on AI for data analysis and decision-making, which could potentially elevate their efficiency and output if optimally leveraged. However, it's essential to focus on developing strategic thinking and creative problem-solving skills for continued growth and improvement."
    },
    {
        "team_name": "ABC",
        "commit_count": 12,
        "additions": 1234,
        "deletions": 1123,
        "churn_rate": 12.0,
        "productivity_score": 12.1,
        "is_finalized": true,
        "final_review": "Team ABC demonstrates a proficient understanding of code adjustments, with an average score of 13. This suggests a steady level of performance. While they have not shown extensive use of AI, their work indicates attention to detail and problem-solving skills. Continued focus on optimization and complexity management is recommended for further growth."
    }
]
```

> **Note**: `hourly_commits` and `hourly_volume` are indexed by relative event hour (index 0 = Hr 1 of event, index 1 = Hr 2, etc.), not clock time.