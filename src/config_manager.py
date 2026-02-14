"""
Configuration Manager
Handles loading and validation of configuration from environment variables and YAML files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration from environment variables and config files."""
    
    def __init__(self, config_dir: str = "config"):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self.env_loaded = False
        
    def load_env(self, env_file: str = ".env") -> None:
        """Load environment variables from .env file.
        
        Args:
            env_file: Path to .env file
        """
        if load_dotenv(env_file):
            self.env_loaded = True
            logger.info(f"Loaded environment variables from {env_file}")
        else:
            logger.warning(f"Could not load {env_file}, using existing environment variables")
    
    def get_github_token(self) -> str:
        """Get GitHub personal access token from environment.
        
        Returns:
            GitHub token
            
        Raises:
            ValueError: If token is not set
        """
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError(
                "GITHUB_TOKEN not found in environment variables. "
                "Please set it in .env file or environment."
            )
        return token
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration settings.
        
        Returns:
            Dictionary with API configuration
        """
        return {
            "api_url": os.getenv("GITHUB_API_URL", "https://api.github.com"),
            "timeout": int(os.getenv("GITHUB_API_TIMEOUT", "30")),
            "max_retries": int(os.getenv("MAX_RETRIES", "3")),
            "rate_limit_buffer": int(os.getenv("RATE_LIMIT_BUFFER", "10")),
            "max_commits_per_request": int(os.getenv("MAX_COMMITS_PER_REQUEST", "100"))
        }
    
    def get_output_config(self) -> Dict[str, str]:
        """Get output configuration settings.
        
        Returns:
            Dictionary with output configuration
        """
        return {
            "format": os.getenv("OUTPUT_FORMAT", "json"),
            "directory": os.getenv("OUTPUT_DIR", "output"),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "log_dir": os.getenv("LOG_DIR", "logs")
        }
    
    def load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """Load configuration from YAML file.
        
        Args:
            filename: Name of YAML file in config directory
            
        Returns:
            Parsed YAML configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration from {config_path}")
        return config or {}
    
    def load_team_mapping(self) -> Dict[str, Any]:
        """Load team mapping configuration.
        
        Returns:
            Team mapping configuration
        """
        try:
            return self.load_yaml_config("teams.yaml")
        except FileNotFoundError:
            logger.warning("teams.yaml not found, using empty team mapping")
            return {"teams": {}, "default_team": "unassigned"}
    
    def load_repositories(self) -> List[Dict[str, Any]]:
        """Load repository configuration.
        
        Returns:
            List of repository configurations
        """
        try:
            config = self.load_yaml_config("repositories.yaml")
            repos = config.get("repositories", [])
            # Filter only enabled repositories
            return [r for r in repos if r.get("enabled", True)]
        except FileNotFoundError:
            logger.warning("repositories.yaml not found, using empty repository list")
            return []
    
    def get_filter_config(self) -> Dict[str, Any]:
        """Get global filter configuration.
        
        Returns:
            Filter configuration
        """
        try:
            config = self.load_yaml_config("repositories.yaml")
            return config.get("filters", {})
        except FileNotFoundError:
            return {}
    
    def validate_config(self) -> bool:
        """Validate that all required configuration is present.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Check GitHub token
        try:
            self.get_github_token()
        except ValueError as e:
            raise ValueError(f"Configuration validation failed: {e}")
        
        # Check if at least one repository is configured
        repos = self.load_repositories()
        if not repos:
            logger.warning("No repositories configured for data collection")
        
        return True