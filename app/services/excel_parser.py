import pandas as pd
from typing import List, Dict, Any
import io

class ExcelParserService:
    @staticmethod
    def parse_repo_file(file_content: bytes) -> List[Dict[str, Any]]:
        try:
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = [c.strip().lower() for c in df.columns]
            
            required = ['teamname', 'team_github_repo']
            missing = [c for c in required if c not in df.columns]
            if missing:
                raise ValueError(f"Missing columns: {', '.join(missing)}")
            
            repos = []
            for _, row in df.iterrows():
                repo = {
                    "url": row['team_github_repo'].strip(),
                    "team": row['teamname'].strip(),
                    "branch": 'main'
                }
                repos.append(repo)
                
            return repos
            
        except Exception as e:
            raise ValueError(f"Parse error: {str(e)}")
