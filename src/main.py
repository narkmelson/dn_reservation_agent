"""
Main entry point for the Date Night Reservation Agent.

This will eventually launch the backend service and integrate with the React frontend.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config
from utils.logger import setup_logger
from clients.google_sheets_client import GoogleSheetsClient


logger = setup_logger(__name__)


def main():
    """
    Main application entry point.
    """
    logger.info("Starting Date Night Reservation Agent")

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        print("\nConfiguration errors found. Please check .env file and credentials.")
        return 1

    logger.info("Configuration validated successfully")

    # Test Google Sheets connection
    try:
        logger.info("Initializing Google Sheets client")
        sheets_client = GoogleSheetsClient()

        logger.info("Fetching restaurants from Google Sheets")
        restaurants = sheets_client.get_all_restaurants()

        print(f"\n✅ Successfully connected to Google Sheets!")
        print(f"Found {len(restaurants)} restaurants in the list\n")

        if restaurants:
            print("Sample restaurants:")
            for i, restaurant in enumerate(restaurants[:3], 1):
                print(f"{i}. {restaurant['restaurant_name']} - {restaurant['cuisine_type']}")

    except Exception as e:
        logger.error(f"Failed to initialize: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}")
        return 1

    logger.info("Application initialized successfully")
    print("\n✅ Date Night Reservation Agent is ready!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
