"""
Data Models
Defines structured data models for commits and file changes.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class FileChange:
    """Represents changes to a single file in a commit."""
    
    filename: str
    status: str  # added, modified, deleted, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None  # Optional: actual diff content
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CommitData:
    """Represents a single commit with all its metadata."""
    
    # Repository information
    repository_name: str
    repository_owner: str
    repository_url: str
    
    # Commit metadata
    commit_sha: str
    commit_message: str
    commit_date: datetime
    commit_url: str
    
    # Author information
    author_name: str
    author_username: Optional[str]
    author_email: str
    
    # Team information
    team_name: str
    
    # Commit statistics
    total_additions: int
    total_deletions: int
    total_changes: int
    files_changed_count: int
    
    # Branch information
    branch: str
    
    # File changes
    file_changes: List[FileChange] = field(default_factory=list)
    
    def to_dict(self, include_patch: bool = False) -> dict:
        """Convert to dictionary.
        
        Args:
            include_patch: Whether to include patch content in file changes
            
        Returns:
            Dictionary representation
        """
        data = {
            "repository": {
                "name": self.repository_name,
                "owner": self.repository_owner,
                "url": self.repository_url
            },
            "commit": {
                "sha": self.commit_sha,
                "message": self.commit_message,
                "date": self.commit_date.isoformat(),
                "url": self.commit_url,
                "branch": self.branch
            },
            "author": {
                "name": self.author_name,
                "username": self.author_username,
                "email": self.author_email,
                "team": self.team_name
            },
            "statistics": {
                "total_additions": self.total_additions,
                "total_deletions": self.total_deletions,
                "total_changes": self.total_changes,
                "files_changed": self.files_changed_count
            },
            "file_changes": []
        }
        
        # Add file changes
        for fc in self.file_changes:
            fc_dict = fc.to_dict()
            if not include_patch:
                fc_dict.pop("patch", None)
            data["file_changes"].append(fc_dict)
        
        return data
    
    def to_flat_dict(self) -> dict:
        """Convert to flat dictionary for CSV export.
        
        Returns:
            Flattened dictionary
        """
        return {
            "repository_name": self.repository_name,
            "repository_owner": self.repository_owner,
            "repository_url": self.repository_url,
            "commit_sha": self.commit_sha,
            "commit_message": self.commit_message,
            "commit_date": self.commit_date.isoformat(),
            "commit_url": self.commit_url,
            "branch": self.branch,
            "author_name": self.author_name,
            "author_username": self.author_username,
            "author_email": self.author_email,
            "team_name": self.team_name,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "total_changes": self.total_changes,
            "files_changed_count": self.files_changed_count
        }


@dataclass
class RepositoryStats:
    """Aggregated statistics for a repository."""
    
    repository_name: str
    repository_owner: str
    total_commits: int
    total_additions: int
    total_deletions: int
    total_files_changed: int
    unique_authors: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    teams_involved: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "repository": f"{self.repository_owner}/{self.repository_name}",
            "total_commits": self.total_commits,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "total_files_changed": self.total_files_changed,
            "unique_authors": self.unique_authors,
            "date_range": {
                "start": self.date_range_start.isoformat() if self.date_range_start else None,
                "end": self.date_range_end.isoformat() if self.date_range_end else None
            },
            "teams_involved": self.teams_involved
        }


@dataclass
class CollectionMetadata:
    """Metadata about the data collection process."""
    
    collection_date: datetime
    total_repositories: int
    total_commits_collected: int
    repositories_processed: List[str]
    filters_applied: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "collection_date": self.collection_date.isoformat(),
            "total_repositories": self.total_repositories,
            "total_commits_collected": self.total_commits_collected,
            "repositories_processed": self.repositories_processed,
            "filters_applied": self.filters_applied
        }