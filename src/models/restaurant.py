"""
Restaurant data model

Defines the Restaurant class matching the Google Sheets schema (FR-2.1)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Restaurant:
    """
    Restaurant data model matching Google Sheets structure.

    Based on PRD FR-2.1 requirements.
    """

    restaurant_name: str
    booking_website: str = ""
    brief_description: str = ""
    yelp_review_avg: Optional[float] = None
    recommendation_source: str = ""
    price_range: str = ""  # $, $$, $$$, $$$$
    cuisine_type: str = ""
    priority_rank: str = ""  # Top, Great, Good, Medium, Low
    date_added: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))

    def to_sheets_row(self) -> list:
        """
        Convert restaurant to Google Sheets row format.

        Returns:
            List of values in correct column order for Google Sheets
        """
        return [
            self.restaurant_name,
            self.booking_website,
            self.brief_description,
            str(self.yelp_review_avg) if self.yelp_review_avg else "",
            self.recommendation_source,
            self.price_range,
            self.cuisine_type,
            self.priority_rank,
            self.date_added
        ]

    @classmethod
    def from_sheets_row(cls, row: list) -> 'Restaurant':
        """
        Create Restaurant instance from Google Sheets row.

        Args:
            row: List of values from Google Sheets (9 columns)

        Returns:
            Restaurant instance
        """
        # Pad row if needed
        row = row + [''] * (9 - len(row))

        return cls(
            restaurant_name=row[0],
            booking_website=row[1],
            brief_description=row[2],
            yelp_review_avg=float(row[3]) if row[3] else None,
            recommendation_source=row[4],
            price_range=row[5],
            cuisine_type=row[6],
            priority_rank=row[7],
            date_added=row[8]
        )

    def __str__(self) -> str:
        """String representation of restaurant"""
        return f"{self.restaurant_name} ({self.cuisine_type}, {self.price_range})"
