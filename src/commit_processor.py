"""
Commit Processor
Processes raw GitHub API commit data into structured models.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dateutil import parser as date_parser

from src.models import CommitData, FileChange
from src.team_mapper import TeamMapper

logger = logging.getLogger(__name__)


class CommitProcessor:
    """Processes commit data from GitHub API into structured models."""
    
    def __init__(self, team_mapper: TeamMapper):
        """Initialize commit processor.
        
        Args:
            team_mapper: TeamMapper instance for author-to-team mapping
        """
        self.team_mapper = team_mapper
        logger.info("Commit processor initialized")
    
    def process_commit(self, commit_data: Dict[str, Any], 
                      repo_owner: str, repo_name: str, 
                      repo_url: str, branch: str,
                      detailed_data: Optional[Dict[str, Any]] = None) -> CommitData:
        """Process a single commit into structured CommitData.
        
        Args:
            commit_data: Raw commit data from GitHub API
            repo_owner: Repository owner
            repo_name: Repository name
            repo_url: Repository URL
            branch: Branch name
            detailed_data: Optional detailed commit data (includes file changes)
            
        Returns:
            Structured CommitData object
        """
        # Use detailed data if provided, otherwise use basic commit data
        data = detailed_data if detailed_data else commit_data
        
        # Extract commit information
        commit_info = data.get("commit", {})
        author_info = commit_info.get("author", {})
        
        # Extract author details
        author_name = author_info.get("name", "Unknown")
        author_email = author_info.get("email", "")
        
        # Get GitHub username (may be None for commits without GitHub account)
        author_username = None
        if "author" in data and data["author"]:
            author_username = data["author"].get("login")
        
        # Map author to team
        team_name = self.team_mapper.get_team(author_username)
        
        # Extract commit date
        commit_date_str = author_info.get("date", "")
        try:
            commit_date = date_parser.parse(commit_date_str)
        except Exception as e:
            logger.warning(f"Could not parse commit date '{commit_date_str}': {e}")
            commit_date = datetime.now()
        
        # Extract statistics
        stats = data.get("stats", {})
        total_additions = stats.get("additions", 0)
        total_deletions = stats.get("deletions", 0)
        total_changes = stats.get("total", total_additions + total_deletions)
        
        # Process file changes
        file_changes = self._process_file_changes(data.get("files", []))
        files_changed_count = len(file_changes)
        
        # Create CommitData object
        commit_obj = CommitData(
            repository_name=repo_name,
            repository_owner=repo_owner,
            repository_url=repo_url,
            commit_sha=data.get("sha", ""),
            commit_message=commit_info.get("message", ""),
            commit_date=commit_date,
            commit_url=data.get("html_url", ""),
            author_name=author_name,
            author_username=author_username,
            author_email=author_email,
            team_name=team_name,
            total_additions=total_additions,
            total_deletions=total_deletions,
            total_changes=total_changes,
            files_changed_count=files_changed_count,
            branch=branch,
            file_changes=file_changes
        )
        
        logger.debug(
            f"Processed commit {commit_obj.commit_sha[:7]} by "
            f"{commit_obj.author_name} ({commit_obj.team_name})"
        )
        
        return commit_obj
    
    def _process_file_changes(self, files_data: List[Dict[str, Any]]) -> List[FileChange]:
        """Process file changes from commit data.
        
        Args:
            files_data: List of file change data from GitHub API
            
        Returns:
            List of FileChange objects
        """
        file_changes = []
        
        for file_data in files_data:
            file_change = FileChange(
                filename=file_data.get("filename", ""),
                status=file_data.get("status", "modified"),
                additions=file_data.get("additions", 0),
                deletions=file_data.get("deletions", 0),
                changes=file_data.get("changes", 0),
                patch=file_data.get("patch")  # Optional diff content
            )
            file_changes.append(file_change)
        
        return file_changes
    
    def process_commits_batch(self, commits_data: List[Dict[str, Any]],
                              repo_owner: str, repo_name: str,
                              repo_url: str, branch: str,
                              detailed_commits: Optional[Dict[str, Dict]] = None) -> List[CommitData]:
        """Process a batch of commits.
        
        Args:
            commits_data: List of raw commit data from GitHub API
            repo_owner: Repository owner
            repo_name: Repository name
            repo_url: Repository URL
            branch: Branch name
            detailed_commits: Optional dict mapping SHA to detailed commit data
            
        Returns:
            List of processed CommitData objects
        """
        processed_commits = []
        
        for commit_data in commits_data:
            sha = commit_data.get("sha")
            detailed = detailed_commits.get(sha) if detailed_commits else None
            
            try:
                commit_obj = self.process_commit(
                    commit_data, repo_owner, repo_name, 
                    repo_url, branch, detailed
                )
                processed_commits.append(commit_obj)
            except Exception as e:
                logger.error(f"Error processing commit {sha}: {e}")
                continue
        
        logger.info(f"Processed {len(processed_commits)} commits for {repo_owner}/{repo_name}")
        return processed_commits
    
    def filter_commits(self, commits: List[CommitData],
                      date_from: Optional[datetime] = None,
                      date_to: Optional[datetime] = None,
                      authors: Optional[List[str]] = None,
                      teams: Optional[List[str]] = None) -> List[CommitData]:
        """Filter commits based on criteria.
        
        Args:
            commits: List of CommitData objects
            date_from: Filter commits after this date
            date_to: Filter commits before this date
            authors: Filter by author usernames
            teams: Filter by team names
            
        Returns:
            Filtered list of CommitData objects
        """
        filtered = commits
        
        # Date filtering
        if date_from:
            filtered = [c for c in filtered if c.commit_date >= date_from]
            logger.debug(f"Filtered to commits after {date_from}: {len(filtered)} remaining")
        
        if date_to:
            filtered = [c for c in filtered if c.commit_date <= date_to]
            logger.debug(f"Filtered to commits before {date_to}: {len(filtered)} remaining")
        
        # Author filtering
        if authors:
            authors_lower = [a.lower() for a in authors]
            filtered = [
                c for c in filtered 
                if c.author_username and c.author_username.lower() in authors_lower
            ]
            logger.debug(f"Filtered to authors {authors}: {len(filtered)} remaining")
        
        # Team filtering
        if teams:
            filtered = [c for c in filtered if c.team_name in teams]
            logger.debug(f"Filtered to teams {teams}: {len(filtered)} remaining")
        
        logger.info(f"Filtering complete: {len(filtered)} commits out of {len(commits)}")
        return filtered