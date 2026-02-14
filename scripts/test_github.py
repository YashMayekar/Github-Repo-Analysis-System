import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.github_client import GitHubAPIClient
from datetime import datetime, timedelta
from app.core.config import settings

gc = GitHubAPIClient(settings.GITHUB_TOKEN)

# Fetch all recent commits
print("=== ALL COMMITS (no since filter) ===")
commits = gc.get_commits('Huuffy', 'test', branch='main', per_page=5)
print(f"Total: {len(commits)}")
for c in commits[:5]:
    sha = c['sha'][:8]
    date = c['commit']['author']['date']
    msg = c['commit']['message'][:60]
    print(f"  {sha} | {date} | {msg}")

# Try with since = 1 hour ago
since_val = (datetime.utcnow() - timedelta(hours=1)).isoformat()
print(f"\n=== COMMITS SINCE 1h AGO ({since_val}) ===")
filtered = gc.get_commits('Huuffy', 'test', branch='main', per_page=5, since=since_val)
print(f"Total: {len(filtered)}")
for c in filtered[:5]:
    sha = c['sha'][:8]
    date = c['commit']['author']['date']
    msg = c['commit']['message'][:60]
    print(f"  {sha} | {date} | {msg}")

# Try with since = 24 hours ago
since_val2 = (datetime.utcnow() - timedelta(hours=24)).isoformat()
print(f"\n=== COMMITS SINCE 24h AGO ({since_val2}) ===")
filtered2 = gc.get_commits('Huuffy', 'test', branch='main', per_page=5, since=since_val2)
print(f"Total: {len(filtered2)}")
for c in filtered2[:5]:
    sha = c['sha'][:8]
    date = c['commit']['author']['date']
    msg = c['commit']['message'][:60]
    print(f"  {sha} | {date} | {msg}")
