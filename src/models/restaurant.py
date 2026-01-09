"""
Restaurant data model

Defines the Restaurant class matching the Google Sheets schema for RestaurantList Agent
"""

from typing import TypedDict
from datetime import datetime


class Restaurant(TypedDict):
    """
    Restaurant data model matching Google Sheets structure.

    Schema based on RestaurantListAgent.md specification.
    """
    name: str
    booking_website: str
    description: str
    price_range: str  # "$", "$$", "$$$", "$$$$"
    cuisine_type: str
    # Source-specific rankings (1.0-5.0, 0.0 if not ranked by source)
    eater_dc_rank: float
    michelin_guide_rank: float
    washington_post_rank: float
    washingtonian_rank: float
    infatuation_rank: float
    # Overall priority rank (average of source rankings)
    priority_rank: float  # 1.0 - 5.0
    priority_reasons: str
    date_added: str  # YYYY-MM-DD format


def create_restaurant(
    name: str,
    booking_website: str = "",
    description: str = "",
    price_range: str = "",
    cuisine_type: str = "",
    eater_dc_rank: float = 0.0,
    michelin_guide_rank: float = 0.0,
    washington_post_rank: float = 0.0,
    washingtonian_rank: float = 0.0,
    infatuation_rank: float = 0.0,
    priority_rank: float = 0.0,
    priority_reasons: str = "",
    date_added: str = ""
) -> Restaurant:
    """
    Create a Restaurant dictionary with proper defaults.

    Args:
        name: Restaurant name (required)
        booking_website: URL for booking (OpenTable/Resy/Tock/restaurant site)
        description: 1-3 sentence description
        price_range: $, $$, $$$, or $$$$
        cuisine_type: Italian, French, Japanese, etc.
        eater_dc_rank: Eater DC ranking (1.0-5.0, 0.0 if not ranked)
        michelin_guide_rank: Michelin Guide ranking (1.0-5.0, 0.0 if not ranked)
        washington_post_rank: Washington Post ranking (1.0-5.0, 0.0 if not ranked)
        washingtonian_rank: Washingtonian ranking (1.0-5.0, 0.0 if not ranked)
        infatuation_rank: Infatuation ranking (1.0-5.0, 0.0 if not ranked)
        priority_rank: Overall priority rank (average of source rankings, 1.0-5.0)
        priority_reasons: 1-3 sentences explaining priority
        date_added: Date in YYYY-MM-DD format (auto-generated if not provided)

    Returns:
        Restaurant dictionary
    """
    if not date_added:
        date_added = datetime.now().strftime('%Y-%m-%d')

    return Restaurant(
        name=name,
        booking_website=booking_website,
        description=description,
        price_range=price_range,
        cuisine_type=cuisine_type,
        eater_dc_rank=eater_dc_rank,
        michelin_guide_rank=michelin_guide_rank,
        washington_post_rank=washington_post_rank,
        washingtonian_rank=washingtonian_rank,
        infatuation_rank=infatuation_rank,
        priority_rank=priority_rank,
        priority_reasons=priority_reasons,
        date_added=date_added
    )


def restaurant_to_sheets_row(restaurant: Restaurant) -> list:
    """
    Convert restaurant to Google Sheets row format.

    Args:
        restaurant: Restaurant dictionary

    Returns:
        List of values in correct column order for Google Sheets (13 columns)
    """
    return [
        restaurant['name'],
        restaurant['booking_website'],
        restaurant['description'],
        restaurant['priority_reasons'],
        restaurant['price_range'],
        restaurant['cuisine_type'],
        restaurant['eater_dc_rank'],
        restaurant['michelin_guide_rank'],
        restaurant['washington_post_rank'],
        restaurant['washingtonian_rank'],
        restaurant['infatuation_rank'],
        restaurant['priority_rank'],
        restaurant['date_added']
    ]


def restaurant_from_sheets_row(row: list) -> Restaurant:
    """
    Create Restaurant from Google Sheets row.

    Args:
        row: List of values from Google Sheets (13 columns)

    Returns:
        Restaurant dictionary
    """
    # Pad row if needed
    row = row + [''] * (13 - len(row))

    return Restaurant(
        name=row[0],
        booking_website=row[1],
        description=row[2],
        priority_reasons=row[3],
        price_range=row[4],
        cuisine_type=row[5],
        eater_dc_rank=float(row[6]) if row[6] else 0.0,
        michelin_guide_rank=float(row[7]) if row[7] else 0.0,
        washington_post_rank=float(row[8]) if row[8] else 0.0,
        washingtonian_rank=float(row[9]) if row[9] else 0.0,
        infatuation_rank=float(row[10]) if row[10] else 0.0,
        priority_rank=float(row[11]) if row[11] else 0.0,
        date_added=row[12]
    )
