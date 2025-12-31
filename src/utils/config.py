"""
Configuration management for the Date Night Reservation Agent.

Loads and validates environment variables from .env file.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

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
