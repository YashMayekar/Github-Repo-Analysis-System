"""
GitHub API Client
Handles authentication and API interactions with GitHub.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class GitHubAPIClient:
    """Client for interacting with GitHub API."""
    
    def __init__(self, token: str, api_url: str = "https://api.github.com", 
                 timeout: int = 30, max_retries: int = 3, rate_limit_buffer: int = 10):
        """Initialize GitHub API client.
        
        Args:
            token: GitHub personal access token
            api_url: Base URL for GitHub API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            rate_limit_buffer: Minimum remaining requests before pausing
        """
        self.token = token
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_buffer = rate_limit_buffer
        
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logger.info("GitHub API client initialized")
    
    def _check_rate_limit(self) -> None:
        """Check and handle GitHub API rate limit."""
        try:
            response = self.session.get(
                f"{self.api_url}/rate_limit",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            rate_data = response.json()
            core_limit = rate_data["resources"]["core"]
            
            remaining = core_limit["remaining"]
            reset_time = core_limit["reset"]
            
            logger.debug(f"Rate limit: {remaining} requests remaining")
            
            if remaining <= self.rate_limit_buffer:
                reset_datetime = datetime.fromtimestamp(reset_time)
                wait_seconds = reset_time - time.time() + 1
                
                if wait_seconds > 0:
                    logger.warning(
                        f"Rate limit nearly exceeded. Waiting until {reset_datetime} "
                        f"({wait_seconds:.0f} seconds)"
                    )
                    time.sleep(wait_seconds)
        
        except Exception as e:
            logger.warning(f"Could not check rate limit: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, RateLimitError))
    )
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated request to GitHub API with retry logic.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            
        Returns:
            JSON response
            
        Raises:
            RateLimitError: If rate limit is exceeded
            requests.exceptions.RequestException: For other API errors
        """
        self._check_rate_limit()
        
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            # Handle rate limiting
            if response.status_code == 403 and "rate limit" in response.text.lower():
                raise RateLimitError("GitHub API rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            raise
    
    def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Repository information
        """
        endpoint = f"repos/{owner}/{repo}"
        logger.info(f"Fetching repository info: {owner}/{repo}")
        return self._make_request(endpoint)
    
    def get_commits(self, owner: str, repo: str, branch: str = "main",
                   since: Optional[str] = None, until: Optional[str] = None,
                   author: Optional[str] = None, per_page: int = 100) -> List[Dict]:
        """Get commits from a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            since: ISO 8601 date string for filtering commits after this date
            until: ISO 8601 date string for filtering commits before this date
            author: GitHub username to filter commits
            per_page: Number of commits per page
            
        Returns:
            List of commits
        """
        endpoint = f"repos/{owner}/{repo}/commits"
        
        params = {
            "sha": branch,
            "per_page": min(per_page, 100)
        }
        
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        
        all_commits = []
        page = 1
        
        logger.info(f"Fetching commits from {owner}/{repo} (branch: {branch})")
        
        while True:
            params["page"] = page
            commits = self._make_request(endpoint, params)
            
            if not commits:
                break
            
            all_commits.extend(commits)
            logger.debug(f"Fetched page {page}: {len(commits)} commits")
            
            # GitHub returns fewer than requested if on last page
            if len(commits) < per_page:
                break
            
            page += 1
        
        logger.info(f"Total commits fetched: {len(all_commits)}")
        return all_commits
    
    def get_commit_details(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Get detailed information about a specific commit.
        
        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA
            
        Returns:
            Detailed commit information including file changes
        """
        endpoint = f"repos/{owner}/{repo}/commits/{sha}"
        return self._make_request(endpoint)
    
    def get_team_members(self, org: str, team_slug: str) -> List[Dict[str, Any]]:
        """Get members of a GitHub team.
        
        Args:
            org: Organization name
            team_slug: Team slug
            
        Returns:
            List of team members
        """
        endpoint = f"orgs/{org}/teams/{team_slug}/members"
        try:
            return self._make_request(endpoint)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Team not found: {org}/{team_slug}")
                return []
            raise
    
    def test_connection(self) -> bool:
        """Test GitHub API connection and authentication.
        
        Returns:
            True if connection successful
        """
        try:
            response = self.session.get(f"{self.api_url}/user", timeout=self.timeout)
            response.raise_for_status()
            user_data = response.json()
            logger.info(f"Successfully authenticated as: {user_data.get('login', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            return False