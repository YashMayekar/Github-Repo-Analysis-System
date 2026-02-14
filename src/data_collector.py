"""
Data Collector
Main orchestrator for collecting commit data from GitHub repositories.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import urlparse

from src.github_client import GitHubAPIClient
from src.commit_processor import CommitProcessor
from src.team_mapper import TeamMapper
from src.branch_detector import BranchDetector
from src.models import CommitData, RepositoryStats, CollectionMetadata

logger = logging.getLogger(__name__)


class DataCollector:
    """Orchestrates the collection of commit data from GitHub repositories."""
    
    def __init__(self, github_client: GitHubAPIClient, 
                 team_mapper: TeamMapper,
                 fetch_detailed_commits: bool = True,
                 auto_detect_branch: bool = True):
        """Initialize data collector.
        
        Args:
            github_client: GitHubAPIClient instance
            team_mapper: TeamMapper instance
            fetch_detailed_commits: Whether to fetch detailed commit data (includes file changes)
            auto_detect_branch: Whether to auto-detect default branch (main/master)
        """
        self.github_client = github_client
        self.team_mapper = team_mapper
        self.commit_processor = CommitProcessor(team_mapper)
        self.fetch_detailed_commits = fetch_detailed_commits
        self.auto_detect_branch = auto_detect_branch
        
        # Initialize branch detector
        if auto_detect_branch:
            self.branch_detector = BranchDetector(github_client)
            logger.info("Branch auto-detection enabled")
        else:
            self.branch_detector = None
        
        logger.info("Data collector initialized")
    
    def parse_repo_url(self, url: str) -> tuple:
        """Parse GitHub repository URL to extract owner and repo name.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo_name)
            
        Raises:
            ValueError: If URL is invalid
        """
        # Handle different URL formats
        # https://github.com/owner/repo
        # github.com/owner/repo
        # owner/repo
        
        url = url.strip().rstrip('/')
        
        if url.startswith('http'):
            parsed = urlparse(url)
            path = parsed.path.strip('/')
        elif '/' in url:
            path = url
        else:
            raise ValueError(f"Invalid repository URL format: {url}")
        
        parts = path.split('/')
        if len(parts) >= 2:
            owner = parts[-2]
            repo = parts[-1].replace('.git', '')
            return owner, repo
        
        raise ValueError(f"Could not parse owner/repo from URL: {url}")
    
    def collect_repository_commits(self, repo_url: str, 
                                   branch: str = None,
                                   date_from: Optional[str] = None,
                                   date_to: Optional[str] = None,
                                   author: Optional[str] = None) -> List[CommitData]:
        """Collect commits from a single repository.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch name (auto-detected if None and auto_detect_branch=True)
            date_from: ISO 8601 date string for filtering commits after this date
            date_to: ISO 8601 date string for filtering commits before this date
            author: GitHub username to filter commits
            
        Returns:
            List of CommitData objects
        """
        try:
            # Parse repository URL
            owner, repo = self.parse_repo_url(repo_url)
            
            # Auto-detect branch if not provided and auto-detection is enabled
            if branch is None and self.auto_detect_branch and self.branch_detector:
                branch = self.branch_detector.detect_default_branch(owner, repo)
                logger.info(f"Auto-detected branch '{branch}' for {owner}/{repo}")
            elif branch is None:
                branch = "main"  # Default fallback
                logger.info(f"Using default branch 'main' for {owner}/{repo}")
            else:
                # Validate provided branch if auto-detection is enabled
                if self.auto_detect_branch and self.branch_detector:
                    branch = self.branch_detector.get_branch_with_fallback(owner, repo, branch)
            
            logger.info(f"Collecting commits from {owner}/{repo} (branch: {branch})")
            
            # Get repository info
            repo_info = self.github_client.get_repository_info(owner, repo)
            full_repo_url = repo_info.get("html_url", repo_url)
            
            # Fetch commits
            commits = self.github_client.get_commits(
                owner, repo, branch, 
                since=date_from, until=date_to, author=author
            )
            
            if not commits:
                logger.warning(f"No commits found for {owner}/{repo}")
                return []
            
            # Fetch detailed commit data if requested
            detailed_commits = {}
            if self.fetch_detailed_commits:
                logger.info(f"Fetching detailed data for {len(commits)} commits...")
                for i, commit in enumerate(commits, 1):
                    sha = commit.get("sha")
                    if sha:
                        try:
                            detailed = self.github_client.get_commit_details(owner, repo, sha)
                            detailed_commits[sha] = detailed
                            
                            if i % 10 == 0:
                                logger.debug(f"Fetched detailed data for {i}/{len(commits)} commits")
                        except Exception as e:
                            logger.warning(f"Could not fetch details for commit {sha}: {e}")
            
            # Process commits
            processed_commits = self.commit_processor.process_commits_batch(
                commits, owner, repo, full_repo_url, branch, detailed_commits
            )
            
            logger.info(f"Successfully collected {len(processed_commits)} commits from {owner}/{repo}")
            return processed_commits
        
        except Exception as e:
            logger.error(f"Error collecting commits from {repo_url}: {e}")
            raise
    
    def collect_multiple_repositories(self, repos_config: List[Dict[str, Any]],
                                     global_filters: Optional[Dict] = None) -> List[CommitData]:
        """Collect commits from multiple repositories.
        
        Args:
            repos_config: List of repository configurations
            global_filters: Global filter settings
            
        Returns:
            Combined list of CommitData objects from all repositories
        """
        all_commits = []
        global_filters = global_filters or {}
        
        for repo_config in repos_config:
            try:
                url = repo_config.get("url")
                branch = repo_config.get("branch")  # May be None for auto-detection
                
                # Merge global and repo-specific filters
                filters = {**global_filters, **repo_config.get("filters", {})}
                
                commits = self.collect_repository_commits(
                    url, branch,
                    date_from=filters.get("date_from"),
                    date_to=filters.get("date_to"),
                    author=filters.get("author")
                )
                
                all_commits.extend(commits)
                
            except Exception as e:
                logger.error(f"Failed to collect from repository {repo_config.get('url')}: {e}")
                continue
        
        logger.info(f"Collected total of {len(all_commits)} commits from {len(repos_config)} repositories")
        return all_commits
    
    def calculate_repository_stats(self, commits: List[CommitData]) -> List[RepositoryStats]:
        """Calculate statistics for each repository.
        
        Args:
            commits: List of CommitData objects
            
        Returns:
            List of RepositoryStats objects
        """
        # Group commits by repository
        repo_commits = {}
        for commit in commits:
            repo_key = f"{commit.repository_owner}/{commit.repository_name}"
            if repo_key not in repo_commits:
                repo_commits[repo_key] = []
            repo_commits[repo_key].append(commit)
        
        # Calculate stats for each repository
        stats_list = []
        for repo_key, repo_commit_list in repo_commits.items():
            owner, name = repo_key.split('/')
            
            # Get unique authors and teams
            authors = set(c.author_username for c in repo_commit_list if c.author_username)
            teams = set(c.team_name for c in repo_commit_list)
            
            # Get date range
            dates = [c.commit_date for c in repo_commit_list]
            date_start = min(dates) if dates else None
            date_end = max(dates) if dates else None
            
            stats = RepositoryStats(
                repository_name=name,
                repository_owner=owner,
                total_commits=len(repo_commit_list),
                total_additions=sum(c.total_additions for c in repo_commit_list),
                total_deletions=sum(c.total_deletions for c in repo_commit_list),
                total_files_changed=sum(c.files_changed_count for c in repo_commit_list),
                unique_authors=len(authors),
                date_range_start=date_start,
                date_range_end=date_end,
                teams_involved=sorted(list(teams))
            )
            stats_list.append(stats)
        
        logger.info(f"Calculated statistics for {len(stats_list)} repositories")
        return stats_list
    
    def create_collection_metadata(self, commits: List[CommitData],
                                   repos_config: List[Dict[str, Any]],
                                   filters: Dict[str, Any]) -> CollectionMetadata:
        """Create metadata about the collection process.
        
        Args:
            commits: List of collected commits
            repos_config: Repository configurations
            filters: Applied filters
            
        Returns:
            CollectionMetadata object
        """
        repo_names = [
            f"{self.parse_repo_url(r['url'])[0]}/{self.parse_repo_url(r['url'])[1]}"
            for r in repos_config
        ]
        
        metadata = CollectionMetadata(
            collection_date=datetime.now(),
            total_repositories=len(repos_config),
            total_commits_collected=len(commits),
            repositories_processed=repo_names,
            filters_applied=filters
        )
        
        return metadata