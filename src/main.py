# #!/usr/bin/env python3
# """
# GitHub Commit Data Collector - Main Entry Point
# Collects and structures commit data from GitHub repositories.
# """

# import argparse
# import sys
# import logging
# from pathlib import Path
# from datetime import datetime

# # Add src to path
# sys.path.insert(0, str(Path(__file__).parent))

# from src.config_manager import ConfigManager
# from src.github_client import GitHubAPIClient
# from src.team_mapper import TeamMapper
# from src.data_collector import DataCollector
# from src.data_exporter import DataExporter
# from src.commit_processor import CommitProcessor
# from src.logger import setup_logging

# logger = logging.getLogger(__name__)


# def parse_arguments():
#     """Parse command line arguments."""
#     parser = argparse.ArgumentParser(
#         description="GitHub Commit Data Collector - Fetch and structure commit data",
#         formatter_class=argparse.RawDescriptionHelpFormatter,
#         epilog="""
# Examples:
#   # Collect from repositories defined in config/repositories.yaml
#   python main.py
  
#   # Collect from a specific repository
#   python main.py --repo https://github.com/owner/repo
  
#   # Collect with date filter
#   python main.py --date-from 2024-01-01 --date-to 2024-12-31
  
#   # Collect and export as CSV
#   python main.py --format csv
  
#   # Collect from specific branch
#   python main.py --repo https://github.com/owner/repo --branch develop
#         """
#     )
    
#     # Repository options
#     parser.add_argument(
#         '--repo', '--repository',
#         help='GitHub repository URL (overrides config file)'
#     )
#     parser.add_argument(
#         '--branch',
#         default='main',
#         help='Branch name (default: main)'
#     )
    
#     # Filter options
#     parser.add_argument(
#         '--date-from',
#         help='Filter commits after this date (ISO format: YYYY-MM-DD)'
#     )
#     parser.add_argument(
#         '--date-to',
#         help='Filter commits before this date (ISO format: YYYY-MM-DD)'
#     )
#     parser.add_argument(
#         '--author',
#         help='Filter commits by author username'
#     )
#     parser.add_argument(
#         '--team',
#         help='Filter commits by team name'
#     )
    
#     # Output options
#     parser.add_argument(
#         '--format',
#         choices=['json', 'csv', 'both'],
#         default='json',
#         help='Output format (default: json)'
#     )
#     parser.add_argument(
#         '--output-dir',
#         default='output',
#         help='Output directory (default: output)'
#     )
#     parser.add_argument(
#         '--include-patch',
#         action='store_true',
#         help='Include patch/diff content in JSON output'
#     )
#     parser.add_argument(
#         '--include-file-details',
#         action='store_true',
#         help='Include detailed file changes CSV when using CSV format'
#     )
    
#     # Configuration options
#     parser.add_argument(
#         '--config-dir',
#         default='config',
#         help='Configuration directory (default: config)'
#     )
#     parser.add_argument(
#         '--env-file',
#         default='.env',
#         help='Environment file path (default: .env)'
#     )
    
#     # Logging options
#     parser.add_argument(
#         '--log-level',
#         choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
#         default='INFO',
#         help='Logging level (default: INFO)'
#     )
#     parser.add_argument(
#         '--no-detailed-commits',
#         action='store_true',
#         help='Skip fetching detailed commit data (faster but no file-level changes)'
#     )
    
#     # Actions
#     parser.add_argument(
#         '--test-connection',
#         action='store_true',
#         help='Test GitHub API connection and exit'
#     )
    
#     return parser.parse_args()


# def main():
#     """Main application entry point."""
#     args = parse_arguments()
    
#     # Setup logging
#     setup_logging(
#         log_level=args.log_level,
#         log_dir='logs',
#         log_to_file=False
#     )
    
#     logger.info("=" * 80)
#     logger.info("GitHub Commit Data Collector Starting")
#     logger.info("=" * 80)
    
#     try:
#         # Initialize configuration manager
#         config_manager = ConfigManager(config_dir=args.config_dir)
#         config_manager.load_env(args.env_file)
        
#         # Validate configuration
#         config_manager.validate_config()
        
#         # Get configurations
#         api_config = config_manager.get_api_config()
#         output_config = config_manager.get_output_config()
        
#         # Initialize GitHub client
#         github_client = GitHubAPIClient(
#             token=config_manager.get_github_token(),
#             api_url=api_config["api_url"],
#             timeout=api_config["timeout"],
#             max_retries=api_config["max_retries"],
#             rate_limit_buffer=api_config["rate_limit_buffer"]
#         )
        
#         # Test connection if requested
#         if args.test_connection:
#             logger.info("Testing GitHub API connection...")
#             if github_client.test_connection():
#                 logger.info("✓ Connection test successful!")
#                 return 0
#             else:
#                 logger.error("✗ Connection test failed!")
#                 return 1
        
#         # Initialize team mapper
#         team_config = config_manager.load_team_mapping()
#         team_mapper = TeamMapper(team_config)
        
#         # Initialize data collector
#         data_collector = DataCollector(
#             github_client=github_client,
#             team_mapper=team_mapper,
#             fetch_detailed_commits=not args.no_detailed_commits
#         )
        
#         # Determine repositories to collect from
#         if args.repo:
#             # Single repository from command line
#             repos_config = [{
#                 'url': args.repo,
#                 'branch': args.branch,
#                 'enabled': True
#             }]
#         else:
#             # Multiple repositories from config file
#             repos_config = config_manager.load_repositories()
#             if not repos_config:
#                 logger.error("No repositories configured. Use --repo or configure repositories.yaml")
#                 return 1
        
#         # Prepare filters
#         global_filters = config_manager.get_filter_config()
        
#         # Override with command line arguments
#         if args.date_from:
#             global_filters['date_from'] = args.date_from
#         if args.date_to:
#             global_filters['date_to'] = args.date_to
#         if args.author:
#             global_filters['author'] = args.author
        
#         logger.info(f"Collecting commits from {len(repos_config)} repository(ies)")
#         if global_filters:
#             logger.info(f"Active filters: {global_filters}")
        
#         # Collect commits
#         all_commits = data_collector.collect_multiple_repositories(
#             repos_config, global_filters
#         )
        
#         if not all_commits:
#             logger.warning("No commits collected!")
#             return 0
        
#         # Apply additional filtering if needed
#         processor = CommitProcessor(team_mapper)
#         if args.team:
#             logger.info(f"Filtering by team: {args.team}")
#             all_commits = processor.filter_commits(
#                 all_commits, teams=[args.team]
#             )
        
#         # Calculate statistics
#         repo_stats = data_collector.calculate_repository_stats(all_commits)
        
#         # Create metadata
#         metadata = data_collector.create_collection_metadata(
#             all_commits, repos_config, global_filters
#         )
        
#         # Initialize exporter
#         output_dir = args.output_dir or output_config["directory"]
#         exporter = DataExporter(output_dir=output_dir)
        
#         # Export data
#         logger.info("=" * 80)
#         logger.info("Exporting Data")
#         logger.info("=" * 80)
        
#         output_files = []
        
#         if args.format in ['json', 'both']:
#             json_file = exporter.export_to_json(
#                 all_commits,
#                 include_patch=args.include_patch,
#                 metadata=metadata
#             )
#             output_files.append(json_file)
            
#             # Export additional summaries
#             summary_file = exporter.export_summary(all_commits, repo_stats, metadata)
#             output_files.append(summary_file)
            
#             team_summary_file = exporter.export_team_summary(all_commits)
#             output_files.append(team_summary_file)
        
#         if args.format in ['csv', 'both']:
#             csv_file = exporter.export_to_csv(
#                 all_commits,
#                 include_file_details=args.include_file_details
#             )
#             if csv_file:
#                 output_files.append(csv_file)
        
#         # Export repository stats
#         stats_file = exporter.export_repository_stats(repo_stats)
#         output_files.append(stats_file)
        
#         # Summary
#         logger.info("=" * 80)
#         logger.info("Collection Complete!")
#         logger.info("=" * 80)
#         logger.info(f"Total commits collected: {len(all_commits)}")
#         logger.info(f"Repositories processed: {len(repos_config)}")
#         logger.info(f"Output files created: {len(output_files)}")
#         for f in output_files:
#             logger.info(f"  - {f}")
#         logger.info("=" * 80)
        
#         return 0
    
#     except KeyboardInterrupt:
#         logger.warning("Collection interrupted by user")
#         return 130
    
#     except Exception as e:
#         logger.error(f"Fatal error: {e}", exc_info=True)
#         return 1


# if __name__ == "__main__":
#     sys.exit(main())