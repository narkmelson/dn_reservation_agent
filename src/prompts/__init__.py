"""
Centralized LLM prompts for the Date Night Reservation Agent.

This module separates prompt templates from business logic for:
- Easier maintenance and versioning
- Clear visibility of all prompts in one place
- Simpler prompt iteration and testing

Note: Source-specific ranking is now combined with extraction (see extraction.py).
The ranking module only contains priority_reasons_prompt for generating the final
summary after rankings are aggregated.
"""

from prompts.extraction import (
    restaurant_extraction_prompt,
    price_enrichment_prompt,
)

from prompts.ranking import (
    priority_reasons_prompt,
)

from prompts.editing import (
    edit_command_prompt,
)

__all__ = [
    # Extraction (now includes source ranking)
    "restaurant_extraction_prompt",
    "price_enrichment_prompt",
    # Ranking (priority reasons only - source ranking is in extraction)
    "priority_reasons_prompt",
    # Editing
    "edit_command_prompt",
]
