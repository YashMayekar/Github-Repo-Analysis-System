"""
Data Exporter
Handles exporting commit data to various formats (JSON, CSV).
"""

import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import pandas as pd

from src.models import CommitData, RepositoryStats, CollectionMetadata

logger = logging.getLogger(__name__)


class DataExporter:
    """Exports commit data to various formats."""
    
    def __init__(self, output_dir: str = "output"):
        """Initialize data exporter.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Data exporter initialized with output directory: {self.output_dir}")
    
    def export_to_json(self, commits: List[CommitData], 
                       filename: str = None,
                       include_patch: bool = False,
                       metadata: CollectionMetadata = None) -> str:
        """Export commits to JSON file.
        
        Args:
            commits: List of CommitData objects
            filename: Output filename (auto-generated if None)
            include_patch: Whether to include patch content
            metadata: Optional collection metadata
            
        Returns:
            Path to output file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"commits_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        # Convert commits to dictionaries
        commits_data = [c.to_dict(include_patch=include_patch) for c in commits]
        
        # Build output structure
        output = {
            "commits": commits_data,
            "total_commits": len(commits_data)
        }
        
        # Add metadata if provided
        if metadata:
            output["metadata"] = metadata.to_dict()
        
        # Write to file with pretty formatting
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(commits)} commits to JSON: {output_path}")
        return str(output_path)
    
    def export_to_csv(self, commits: List[CommitData], 
                      filename: str = None,
                      include_file_details: bool = False) -> str:
        """Export commits to CSV file.
        
        Args:
            commits: List of CommitData objects
            filename: Output filename (auto-generated if None)
            include_file_details: Whether to create separate CSV for file changes
            
        Returns:
            Path to output file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"commits_{timestamp}.csv"
        
        output_path = self.output_dir / filename
        
        # Convert commits to flat dictionaries for CSV
        commits_data = [c.to_flat_dict() for c in commits]
        
        # Write commits CSV
        if commits_data:
            df = pd.DataFrame(commits_data)
            df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"Exported {len(commits)} commits to CSV: {output_path}")
        else:
            logger.warning("No commits to export to CSV")
            return None
        
        # Optionally export file changes to separate CSV
        if include_file_details:
            file_changes_path = self._export_file_changes_csv(commits, filename)
            logger.info(f"Exported file changes to: {file_changes_path}")
        
        return str(output_path)
    
    def _export_file_changes_csv(self, commits: List[CommitData], 
                                  base_filename: str) -> str:
        """Export file changes to separate CSV.
        
        Args:
            commits: List of CommitData objects
            base_filename: Base filename for output
            
        Returns:
            Path to file changes CSV
        """
        file_changes_filename = base_filename.replace(".csv", "_file_changes.csv")
        output_path = self.output_dir / file_changes_filename
        
        # Build file changes data
        file_changes_data = []
        for commit in commits:
            for fc in commit.file_changes:
                file_changes_data.append({
                    "commit_sha": commit.commit_sha,
                    "commit_date": commit.commit_date.isoformat(),
                    "author_username": commit.author_username,
                    "team_name": commit.team_name,
                    "repository": f"{commit.repository_owner}/{commit.repository_name}",
                    "filename": fc.filename,
                    "status": fc.status,
                    "additions": fc.additions,
                    "deletions": fc.deletions,
                    "changes": fc.changes
                })
        
        if file_changes_data:
            df = pd.DataFrame(file_changes_data)
            df.to_csv(output_path, index=False, encoding='utf-8')
        
        return str(output_path)
    
    def export_repository_stats(self, stats: List[RepositoryStats], 
                                filename: str = None) -> str:
        """Export repository statistics to JSON.
        
        Args:
            stats: List of RepositoryStats objects
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to output file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"repository_stats_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        stats_data = [s.to_dict() for s in stats]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported statistics for {len(stats)} repositories: {output_path}")
        return str(output_path)
    
    def export_summary(self, commits: List[CommitData], 
                       stats: List[RepositoryStats],
                       metadata: CollectionMetadata,
                       filename: str = None) -> str:
        """Export collection summary with metadata and statistics.
        
        Args:
            commits: List of CommitData objects
            stats: List of RepositoryStats objects
            metadata: Collection metadata
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to output file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"collection_summary_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        # Calculate additional statistics
        unique_authors = len(set(c.author_username for c in commits if c.author_username))
        unique_teams = len(set(c.team_name for c in commits))
        
        summary = {
            "metadata": metadata.to_dict(),
            "overall_statistics": {
                "total_commits": len(commits),
                "unique_authors": unique_authors,
                "unique_teams": unique_teams,
                "total_additions": sum(c.total_additions for c in commits),
                "total_deletions": sum(c.total_deletions for c in commits),
                "total_files_changed": sum(c.files_changed_count for c in commits)
            },
            "repository_statistics": [s.to_dict() for s in stats]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported collection summary: {output_path}")
        return str(output_path)
    
    def export_team_summary(self, commits: List[CommitData], 
                           filename: str = None) -> str:
        """Export team-level summary statistics.
        
        Args:
            commits: List of CommitData objects
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to output file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"team_summary_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        # Aggregate by team
        team_stats = {}
        for commit in commits:
            team = commit.team_name
            if team not in team_stats:
                team_stats[team] = {
                    "team_name": team,
                    "total_commits": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "total_files_changed": 0,
                    "unique_authors": set()
                }
            
            team_stats[team]["total_commits"] += 1
            team_stats[team]["total_additions"] += commit.total_additions
            team_stats[team]["total_deletions"] += commit.total_deletions
            team_stats[team]["total_files_changed"] += commit.files_changed_count
            if commit.author_username:
                team_stats[team]["unique_authors"].add(commit.author_username)
        
        # Convert sets to counts
        team_summary = []
        for team, stats in team_stats.items():
            stats["unique_authors"] = len(stats["unique_authors"])
            team_summary.append(stats)
        
        # Sort by commit count
        team_summary.sort(key=lambda x: x["total_commits"], reverse=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(team_summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported team summary: {output_path}")
        return str(output_path)