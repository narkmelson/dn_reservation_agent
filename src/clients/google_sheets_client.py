"""
Google Sheets API Client for Date Night Reservation Agent

This module provides functionality to authenticate with Google Sheets API
and manage the "Date Night Restaurant List" spreadsheet.

Based on requirements in GoogleAPI.md and PRD.md (FR-2.1)
"""

import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# OAuth 2.0 scope for Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class GoogleSheetsClient:
    """
    Client for managing Google Sheets operations for the restaurant list.

    Handles authentication, reading, writing, and updating restaurant data
    in the "Date Night Restaurant List" spreadsheet.
    """

    # Column mapping based on FR-2.1 requirements
    COLUMNS = {
        'restaurant_name': 'A',
        'booking_website': 'B',
        'brief_description': 'C',
        'yelp_review_avg': 'D',
        'recommendation_source': 'E',
        'price_range': 'F',
        'cuisine_type': 'G',
        'priority_rank': 'H',
        'date_added': 'I'
    }

    HEADER_ROW = [
        'Restaurant Name',
        'Booking Website',
        'Brief Description',
        'Yelp Review Average',
        'Recommendation Source',
        'Price Range',
        'Cuisine Type',
        'Priority Rank',
        'Date Added'
    ]

    def __init__(self):
        """Initialize the Google Sheets client with credentials from .env"""
        self.spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        self.credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
        self.token_file = os.getenv('GOOGLE_SHEETS_TOKEN_FILE', 'token.json')
        self.sheet_name = os.getenv('GOOGLE_SHEETS_SHEET_NAME', 'Date Night Restaurant List')

        if not self.spreadsheet_id or self.spreadsheet_id == 'your_spreadsheet_id_here':
            raise ValueError(
                "GOOGLE_SHEETS_SPREADSHEET_ID not set in .env file. "
                "Please add your spreadsheet ID from the Google Sheets URL."
            )

        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """
        Authenticate with Google Sheets API using OAuth 2.0.

        On first run, opens browser for user authentication.
        On subsequent runs, uses stored token from token.json.
        Automatically refreshes expired tokens.
        """
        creds = None

        # Check if token.json exists with valid credentials
        if Path(self.token_file).exists():
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh expired token
                print("Refreshing expired token...")
                creds.refresh(Request())
            else:
                # Run OAuth flow for new authentication
                if not Path(self.credentials_file).exists():
                    raise FileNotFoundError(
                        f"Credentials file '{self.credentials_file}' not found. "
                        "Please download OAuth credentials from Google Cloud Console "
                        "and save as credentials.json. See GoogleAPI.md for details."
                    )

                print("Starting authentication flow...")
                print("A browser window will open for you to grant permissions.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
            print(f"Token saved to {self.token_file}")

        # Build the service
        self.service = build('sheets', 'v4', credentials=creds)
        print("Successfully authenticated with Google Sheets API")

    def get_all_restaurants(self) -> List[Dict[str, Any]]:
        """
        Retrieve all restaurants from the spreadsheet.

        Returns:
            List of dictionaries, each containing restaurant data with keys:
            - restaurant_name
            - booking_website
            - brief_description
            - yelp_review_avg
            - recommendation_source
            - price_range
            - cuisine_type
            - priority_rank
            - date_added

        Raises:
            HttpError: If API request fails
        """
        try:
            # Read from row 2 onwards (skip header)
            range_name = f"{self.sheet_name}!A2:I"

            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            if not values:
                print("No restaurants found in spreadsheet")
                return []

            # Convert rows to dictionaries
            restaurants = []
            for row in values:
                # Pad row with empty strings if columns are missing
                row = row + [''] * (9 - len(row))

                restaurant = {
                    'restaurant_name': row[0],
                    'booking_website': row[1],
                    'brief_description': row[2],
                    'yelp_review_avg': row[3],
                    'recommendation_source': row[4],
                    'price_range': row[5],
                    'cuisine_type': row[6],
                    'priority_rank': row[7],
                    'date_added': row[8]
                }
                restaurants.append(restaurant)

            print(f"Retrieved {len(restaurants)} restaurants from spreadsheet")
            return restaurants

        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    def add_restaurant(self, restaurant: Dict[str, Any]) -> bool:
        """
        Add a new restaurant to the spreadsheet.

        Args:
            restaurant: Dictionary containing restaurant data with keys:
                - restaurant_name (required)
                - booking_website
                - brief_description
                - yelp_review_avg
                - recommendation_source
                - price_range
                - cuisine_type
                - priority_rank
                - date_added (auto-generated if not provided)

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If restaurant_name is missing
            HttpError: If API request fails
        """
        if not restaurant.get('restaurant_name'):
            raise ValueError("restaurant_name is required")

        # Auto-generate date_added if not provided
        if not restaurant.get('date_added'):
            restaurant['date_added'] = datetime.now().strftime('%Y-%m-%d')

        # Build row data in correct column order
        row = [
            restaurant.get('restaurant_name', ''),
            restaurant.get('booking_website', ''),
            restaurant.get('brief_description', ''),
            restaurant.get('yelp_review_avg', ''),
            restaurant.get('recommendation_source', ''),
            restaurant.get('price_range', ''),
            restaurant.get('cuisine_type', ''),
            restaurant.get('priority_rank', ''),
            restaurant.get('date_added', '')
        ]

        try:
            values = [row]
            body = {'values': values}

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:I",
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            print(f"Added restaurant: {restaurant['restaurant_name']}")
            print(f"Updated cells: {result.get('updates').get('updatedCells')}")
            return True

        except HttpError as error:
            print(f"An error occurred while adding restaurant: {error}")
            raise

    def add_multiple_restaurants(self, restaurants: List[Dict[str, Any]]) -> bool:
        """
        Add multiple restaurants to the spreadsheet in a single API call.

        Args:
            restaurants: List of restaurant dictionaries

        Returns:
            True if successful, False otherwise

        Raises:
            HttpError: If API request fails
        """
        if not restaurants:
            print("No restaurants to add")
            return True

        rows = []
        for restaurant in restaurants:
            # Auto-generate date_added if not provided
            if not restaurant.get('date_added'):
                restaurant['date_added'] = datetime.now().strftime('%Y-%m-%d')

            row = [
                restaurant.get('restaurant_name', ''),
                restaurant.get('booking_website', ''),
                restaurant.get('brief_description', ''),
                restaurant.get('yelp_review_avg', ''),
                restaurant.get('recommendation_source', ''),
                restaurant.get('price_range', ''),
                restaurant.get('cuisine_type', ''),
                restaurant.get('priority_rank', ''),
                restaurant.get('date_added', '')
            ]
            rows.append(row)

        try:
            body = {'values': rows}

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:I",
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            print(f"Added {len(restaurants)} restaurants")
            print(f"Updated cells: {result.get('updates').get('updatedCells')}")
            return True

        except HttpError as error:
            print(f"An error occurred while adding restaurants: {error}")
            raise

    def update_restaurant(
        self,
        row_number: int,
        restaurant: Dict[str, Any]
    ) -> bool:
        """
        Update an existing restaurant in the spreadsheet.

        Args:
            row_number: The row number to update (2 = first data row after header)
            restaurant: Dictionary with fields to update (only provided fields are updated)

        Returns:
            True if successful, False otherwise

        Raises:
            HttpError: If API request fails
        """
        if row_number < 2:
            raise ValueError("row_number must be 2 or greater (row 1 is header)")

        try:
            # Build update requests for each field
            updates = []

            for field, column in self.COLUMNS.items():
                if field in restaurant:
                    range_name = f"{self.sheet_name}!{column}{row_number}"
                    value = restaurant[field]

                    updates.append({
                        'range': range_name,
                        'values': [[value]]
                    })

            if not updates:
                print("No fields to update")
                return True

            # Batch update all fields
            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': updates
            }

            result = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()

            print(f"Updated restaurant at row {row_number}")
            print(f"Updated cells: {result.get('totalUpdatedCells')}")
            return True

        except HttpError as error:
            print(f"An error occurred while updating restaurant: {error}")
            raise

    def delete_restaurant(self, row_number: int) -> bool:
        """
        Delete a restaurant from the spreadsheet by clearing the row.

        Note: This clears the row content but doesn't remove the row itself.
        Use with caution - consider using a "status" column instead for soft deletes.

        Args:
            row_number: The row number to delete (2 = first data row after header)

        Returns:
            True if successful, False otherwise

        Raises:
            HttpError: If API request fails
        """
        if row_number < 2:
            raise ValueError("row_number must be 2 or greater (row 1 is header)")

        try:
            range_name = f"{self.sheet_name}!A{row_number}:I{row_number}"

            result = self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            print(f"Deleted restaurant at row {row_number}")
            return True

        except HttpError as error:
            print(f"An error occurred while deleting restaurant: {error}")
            raise

    def initialize_spreadsheet(self) -> bool:
        """
        Initialize the spreadsheet with headers if empty.

        Checks if row 1 exists and adds headers if not present.

        Returns:
            True if headers were added or already exist, False otherwise
        """
        try:
            # Check if headers exist
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:I1"
            ).execute()

            values = result.get('values', [])

            if values and len(values[0]) == 9:
                print("Headers already exist")
                return True

            # Add headers
            body = {'values': [self.HEADER_ROW]}

            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:I1",
                valueInputOption='RAW',
                body=body
            ).execute()

            print("Added headers to spreadsheet")
            return True

        except HttpError as error:
            print(f"An error occurred while initializing spreadsheet: {error}")
            raise


def main():
    """
    Example usage and testing of GoogleSheetsClient
    """
    try:
        # Initialize client
        print("Initializing Google Sheets client...")
        client = GoogleSheetsClient()

        # Initialize spreadsheet with headers
        print("\nInitializing spreadsheet...")
        client.initialize_spreadsheet()

        # Get all restaurants
        print("\nFetching all restaurants...")
        restaurants = client.get_all_restaurants()

        if restaurants:
            print(f"\nFound {len(restaurants)} restaurants:")
            for i, restaurant in enumerate(restaurants, 1):
                print(f"{i}. {restaurant['restaurant_name']} - {restaurant['cuisine_type']}")
        else:
            print("\nNo restaurants in spreadsheet yet")

        # Example: Add a test restaurant (uncomment to test)
        # print("\nAdding test restaurant...")
        # test_restaurant = {
        #     'restaurant_name': 'Test Restaurant',
        #     'booking_website': 'https://example.com',
        #     'brief_description': 'A test entry for validation',
        #     'yelp_review_avg': '4.0',
        #     'recommendation_source': 'Manual Test',
        #     'price_range': '$$',
        #     'cuisine_type': 'American',
        #     'priority_rank': 'Medium'
        # }
        # client.add_restaurant(test_restaurant)

        print("\nGoogle Sheets client test completed successfully!")

    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
