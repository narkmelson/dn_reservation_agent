"""
Configuration management for the Date Night Reservation Agent.

Loads and validates environment variables from .env file.
Loads source configuration from config/sources.yaml.
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
import yaml

# Load environment variables
load_dotenv()


class Config:
    """Application configuration loaded from environment variables"""

    # AI Service API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

    # Restaurant/Booking APIs
    OPENTABLE_API_KEY = os.getenv('OPENTABLE_API_KEY', '')
    YELP_API_KEY = os.getenv('YELP_API_KEY', '')
    RESY_API_KEY = os.getenv('RESY_API_KEY', '')
    TOCK_API_KEY = os.getenv('TOCK_API_KEY', '')

    # Location Preferences
    DEFAULT_CITY = os.getenv('DEFAULT_CITY', 'Washington')
    DEFAULT_STATE = os.getenv('DEFAULT_STATE', 'DC')
    SEARCH_RADIUS_MILES = int(os.getenv('SEARCH_RADIUS_MILES', '10'))

    # Reservation Preferences
    DAY_OF_WEEK = os.getenv('DAY_OF_WEEK', '[Friday, Saturday]')
    TIME_OF_DAY_START = os.getenv('TIME_OF_DAY_START', '5:30PM')
    TIME_OF_DAY_END = os.getenv('TIME_OF_DAY_END', '8:00PM')
    PARTY_SIZE = int(os.getenv('PARTY_SIZE', '2'))

    # Google Sheets Configuration
    GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID', '')
    GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
    GOOGLE_SHEETS_TOKEN_FILE = os.getenv('GOOGLE_SHEETS_TOKEN_FILE', 'token.json')
    GOOGLE_SHEETS_SHEET_NAME = os.getenv('GOOGLE_SHEETS_SHEET_NAME', 'Date Night Restaurant List')

    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / 'data'
    LOGS_DIR = PROJECT_ROOT / 'logs'
    CACHE_DIR = DATA_DIR / 'cache'

    # Cache Configuration
    CACHE_ENABLED = os.getenv('DISABLE_CACHE', '').lower() != 'true'
    CACHE_TTL_HOURS = int(os.getenv('CACHE_TTL_HOURS', '24'))

    @classmethod
    def validate(cls) -> List[str]:
        """
        Validate required configuration values.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not cls.GOOGLE_SHEETS_SPREADSHEET_ID or cls.GOOGLE_SHEETS_SPREADSHEET_ID == 'your_spreadsheet_id_here':
            errors.append("GOOGLE_SHEETS_SPREADSHEET_ID not set in .env")

        if not Path(cls.GOOGLE_SHEETS_CREDENTIALS_FILE).exists():
            errors.append(f"Google credentials file not found: {cls.GOOGLE_SHEETS_CREDENTIALS_FILE}")

        # Create directories if they don't exist
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.CACHE_DIR.mkdir(exist_ok=True)

        return errors

    @classmethod
    def get_days_of_week(cls) -> List[str]:
        """
        Parse DAY_OF_WEEK from config string.

        Returns:
            List of day names (e.g., ['Friday', 'Saturday'])
        """
        days_str = cls.DAY_OF_WEEK.strip('[]')
        return [day.strip() for day in days_str.split(',')]


# Cache for sources config to avoid repeated file reads
_sources_config_cache: Dict[str, Any] = {}


def load_sources_config() -> Dict[str, Any]:
    """
    Load restaurant source configuration from config/sources.yaml.

    Returns:
        Dict containing:
        - known_urls: Dict[str, List[str]] - source name -> list of URLs
        - search_queries: Dict[str, List[str]] - source name -> list of queries
        - source_domains: Dict[str, str] - source name -> domain

    Raises:
        FileNotFoundError: If config/sources.yaml doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    global _sources_config_cache

    if _sources_config_cache:
        return _sources_config_cache

    config_path = Config.PROJECT_ROOT / 'config' / 'sources.yaml'

    if not config_path.exists():
        raise FileNotFoundError(
            f"Sources config not found: {config_path}\n"
            "Please create config/sources.yaml with known_urls, search_queries, and source_domains."
        )

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Validate required keys
    required_keys = ['known_urls', 'search_queries', 'source_domains']
    for key in required_keys:
        if key not in config:
            config[key] = {}

    _sources_config_cache = config
    return config


def get_known_urls() -> Dict[str, List[str]]:
    """Get known high-value URLs by source."""
    return load_sources_config().get('known_urls', {})


def get_search_queries() -> Dict[str, List[str]]:
    """Get source-specific search queries."""
    return load_sources_config().get('search_queries', {})


def get_source_domains() -> Dict[str, str]:
    """Get source domain mappings."""
    return load_sources_config().get('source_domains', {})


def get_deep_crawl_sources() -> Dict[str, Dict[str, Any]]:
    """
    Get deep crawl source configurations.

    Returns:
        Dict mapping source name to config with:
        - list_url: URL of the list/index page
        - restaurant_url_pattern: Regex pattern to match restaurant pages
        - max_restaurants: Max number of restaurants to extract
    """
    return load_sources_config().get('deep_crawl_sources', {})
