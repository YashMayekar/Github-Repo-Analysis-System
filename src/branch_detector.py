"""
Branch Auto-Detection Utility
Automatically detects the default branch (main/master) for repositories.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BranchDetector:
    """Detects and validates branch names for repositories."""
    
    def __init__(self, github_client):
        """Initialize branch detector.
        
        Args:
            github_client: GitHubAPIClient instance
        """
        self.github_client = github_client
        self._branch_cache = {}  # Cache detected branches
    
    def detect_default_branch(self, owner: str, repo: str) -> str:
        """Auto-detect the default branch for a repository.
        
        Common default branches:
        - main (newer standard)
        - master (older standard)
        - develop
        - trunk
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Default branch name
        """
        cache_key = f"{owner}/{repo}"
        
        # Check cache first
        if cache_key in self._branch_cache:
            logger.debug(f"Using cached branch for {cache_key}: {self._branch_cache[cache_key]}")
            return self._branch_cache[cache_key]
        
        try:
            # Get repository info from GitHub API
            repo_info = self.github_client.get_repository_info(owner, repo)
            default_branch = repo_info.get("default_branch", "main")
            
            logger.info(f"Detected default branch for {owner}/{repo}: {default_branch}")
            
            # Cache the result
            self._branch_cache[cache_key] = default_branch
            
            return default_branch
            
        except Exception as e:
            logger.warning(f"Could not detect default branch for {owner}/{repo}: {e}")
            logger.info(f"Falling back to 'main' branch")
            return "main"
    
    def validate_branch(self, owner: str, repo: str, branch: str) -> bool:
        """Validate if a branch exists in the repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name to validate
            
        Returns:
            True if branch exists, False otherwise
        """
        try:
            # Try to get commits from this branch
            commits = self.github_client.get_commits(
                owner, repo, branch, per_page=1
            )
            return len(commits) > 0
            
        except Exception as e:
            logger.debug(f"Branch '{branch}' validation failed for {owner}/{repo}: {e}")
            return False
    
    def get_branch_with_fallback(self, owner: str, repo: str, 
                                  preferred_branch: Optional[str] = None) -> str:
        """Get branch name with automatic fallback logic.
        
        Priority:
        1. Preferred branch (if provided and exists)
        2. Repository default branch
        3. Try 'main'
        4. Try 'master'
        5. Fallback to 'main' (will fail later if doesn't exist)
        
        Args:
            owner: Repository owner
            repo: Repository name
            preferred_branch: User's preferred branch name
            
        Returns:
            Best available branch name
        """
        # 1. Try preferred branch if provided
        if preferred_branch:
            logger.debug(f"Trying preferred branch: {preferred_branch}")
            if self.validate_branch(owner, repo, preferred_branch):
                logger.info(f"Using preferred branch '{preferred_branch}' for {owner}/{repo}")
                return preferred_branch
            else:
                logger.warning(f"Preferred branch '{preferred_branch}' not found for {owner}/{repo}")
        
        # 2. Try repository's default branch
        logger.debug(f"Detecting default branch for {owner}/{repo}")
        default_branch = self.detect_default_branch(owner, repo)
        
        if self.validate_branch(owner, repo, default_branch):
            logger.info(f"Using default branch '{default_branch}' for {owner}/{repo}")
            return default_branch
        
        # 3. Try common branch names
        common_branches = ["main", "master", "develop", "trunk"]
        for branch in common_branches:
            if branch == default_branch:
                continue  # Already tried
            
            logger.debug(f"Trying common branch: {branch}")
            if self.validate_branch(owner, repo, branch):
                logger.info(f"Using branch '{branch}' for {owner}/{repo}")
                self._branch_cache[f"{owner}/{repo}"] = branch
                return branch
        
        # 4. Fallback (will likely fail in collection, but return something)
        logger.warning(f"Could not find valid branch for {owner}/{repo}, using 'main'")
        return "main"
    
    def clear_cache(self):
        """Clear the branch detection cache."""
        self._branch_cache.clear()
        logger.debug("Branch detection cache cleared")