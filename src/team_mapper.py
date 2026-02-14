"""
Team Mapper
Maps GitHub users to team names based on configuration.
"""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TeamMapper:
    """Maps GitHub usernames to team names."""
    
    def __init__(self, team_config: Dict):
        """Initialize team mapper with configuration.
        
        Args:
            team_config: Team configuration dictionary from YAML
        """
        self.team_config = team_config
        self.default_team = team_config.get("default_team", "unassigned")
        
        # Build username to team mapping
        self.username_to_team: Dict[str, str] = {}
        teams = team_config.get("teams", {})
        
        for team_name, members in teams.items():
            if isinstance(members, list):
                for username in members:
                    self.username_to_team[username.lower()] = team_name
        
        logger.info(f"Team mapper initialized with {len(self.username_to_team)} user mappings")
    
    def get_team(self, username: Optional[str]) -> str:
        """Get team name for a GitHub username.
        
        Args:
            username: GitHub username
            
        Returns:
            Team name
        """
        if not username:
            return self.default_team
        
        username_lower = username.lower()
        team = self.username_to_team.get(username_lower, self.default_team)
        
        logger.debug(f"Mapped user '{username}' to team '{team}'")
        return team
    
    def get_all_teams(self) -> Set[str]:
        """Get set of all configured team names.
        
        Returns:
            Set of team names
        """
        teams = set(self.username_to_team.values())
        teams.add(self.default_team)
        return teams
    
    def get_team_members(self, team_name: str) -> List[str]:
        """Get list of usernames for a specific team.
        
        Args:
            team_name: Team name
            
        Returns:
            List of usernames in the team
        """
        members = [
            username for username, team in self.username_to_team.items()
            if team == team_name
        ]
        return members
    
    def add_mapping(self, username: str, team_name: str) -> None:
        """Dynamically add a username to team mapping.
        
        Args:
            username: GitHub username
            team_name: Team name
        """
        self.username_to_team[username.lower()] = team_name
        logger.debug(f"Added mapping: {username} -> {team_name}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about team mappings.
        
        Returns:
            Dictionary with team statistics
        """
        stats = {}
        for team in self.get_all_teams():
            stats[team] = len(self.get_team_members(team))
        return stats