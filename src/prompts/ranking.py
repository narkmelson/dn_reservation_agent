"""
Prompts for ranking restaurants based on authoritative sources.

Note: Source-specific ranking is now done during extraction (see extraction.py).
This module now only contains prompts for generating priority reasons after
rankings have been aggregated.
"""

# System prompt for priority reasons
PRIORITY_REASONS_SYSTEM = (
    "You are a concise restaurant recommendation writer. Generate brief, "
    "compelling reasons for why a restaurant is prioritized."
)


def priority_reasons_prompt(
    restaurant_name: str,
    description: str,
    priority_rank: float,
    rankings_text: str
) -> str:
    """
    Generate prompt for explaining why a restaurant is prioritized.

    Args:
        restaurant_name: Name of the restaurant
        description: Restaurant description
        priority_rank: Overall priority ranking (1.0-5.0)
        rankings_text: Formatted text of source rankings

    Returns:
        Formatted prompt string
    """
    return f"""Generate a brief explanation (1-3 sentences) for why this restaurant is prioritized for an upscale date night list:

RESTAURANT:
Name: {restaurant_name}
Description: {description}
Overall Ranking: {priority_rank}/5.0

SOURCE RANKINGS:
{rankings_text}

Focus on:
- Notable list placements or awards
- Standout features (food quality, innovation, ambience, cocktails)
- Recent recognition or acclaim

Keep it concise and compelling.

Respond with just the text explanation, no JSON."""
