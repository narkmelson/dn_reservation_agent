"""
Prompts for extracting restaurant data from web content.
"""

# System prompt for restaurant extraction and ranking
RESTAURANT_EXTRACTION_SYSTEM = (
    "You are a restaurant data extraction and ranking assistant. Your job is to parse web "
    "content from authoritative food publications, extract structured information about "
    "restaurants, and rank each restaurant based on how prominently it is featured in the source."
)

# System prompt for price enrichment
PRICE_ENRICHMENT_SYSTEM = (
    "You are a restaurant price analyst. Extract the price tier from search results."
)


def restaurant_extraction_prompt(
    source: str,
    location: str,
    content: str,
    chunk_label: str = ""
) -> str:
    """
    Generate prompt for extracting and ranking restaurants from web content.

    Args:
        source: Name of the source (e.g., "Eater DC", "Michelin Guide")
        location: City/region for filtering (e.g., "Washington DC")
        content: Raw web content to extract from
        chunk_label: Optional label for chunked content (e.g., "(chunk 1/3)")

    Returns:
        Formatted prompt string
    """
    return f"""I found content from {source}{chunk_label}. Extract and rank restaurants that are PRIMARY FEATURED ENTRIES in this content.

GUIDELINES:
- Location: {location} area (include nearby suburbs)
- ONLY extract restaurants that are FEATURED ENTRIES in the list (have their own dedicated section/write-up)
- Include restaurants of any price range (we'll filter later)
- Do NOT skip restaurants because they seem casual - if they're a featured entry, include them

CRITICAL DISTINCTION:
- DO extract: Restaurants with their own heading, description, address, and write-up (these are the featured entries)
- DO NOT extract: Restaurants merely MENTIONED within another restaurant's description (e.g., "same owner as X", "sister restaurant to Y", "team behind Z")
- DO NOT extract: Restaurants mentioned in "See more" or "Related" links
- DO NOT extract: Restaurants mentioned in update notes about what was added/removed from the list

Look for structural indicators of featured entries:
- Numbered or bulleted list items with full details
- H2/H3 headings for each restaurant
- Address, phone, website info for each restaurant
- Multi-sentence descriptions

If a restaurant is just a passing mention (e.g., "the team also runs X"), do NOT include it.

SOURCE CONTENT:
{content}

For each restaurant that meets the criteria, extract AND RANK:

1. Restaurant name (official name)
2. Brief description (1-3 sentences from the article)
3. Cuisine type (e.g., Italian, French, Japanese)
4. Price range - MUST be one of: $, $$, $$$, $$$$ based on typical per-person dinner cost (with one drink):
   - $: Under $25 (fast casual, counter service, cheap eats)
   - $$: $25-50 (casual dining, neighborhood spots)
   - $$$: $50-100 (upscale casual, special occasion worthy)
   - $$$$: Over $100 (fine dining, tasting menus, Michelin-starred)

   INFERENCE RULES when price is not explicitly stated:
   - Tasting menu, omakase, fine dining, Michelin star → $$$$
   - "Upscale", "special occasion", "splurge" → $$$ or $$$$
   - "Casual", "neighborhood", "everyday" → $$
   - Counter service, fast casual, takeout-focused → $
   - If truly unknown, use "" (empty string)

5. Booking website URL (if mentioned, otherwise empty)

6. SOURCE RANK (1.0-5.0) - How prominently is this restaurant featured IN THIS SOURCE?

   RANKING CRITERIA (consider ALL of these):
   - Position in list: Is it #1? Top 3? Top 10? Middle of a long list?
   - Awards/honors: Michelin stars, Bib Gourmand, "Best New Restaurant", Editor's Pick
   - Language intensity: "must-visit", "essential", "game-changing" vs "solid", "worth a try"
   - Prominence: Lead item with photo? Brief mention at the end?
   - Recency: "Hottest new opening" vs established favorite

   RANKING SCALE:
   - 5.0: Exceptional - #1-3 on list, Michelin starred, "best in city", lead feature
   - 4.0: Excellent - Top 10, Bib Gourmand, "essential", prominently featured with strong praise
   - 3.0: Very Good - Featured in list with positive description, recommended
   - 2.0: Good - Included in list but not standout, brief write-up
   - 1.0: Mentioned - Minimal endorsement, filler entry, or mixed review

7. Ranking reason (1 brief sentence explaining the rank based on position/prominence in this source)

Respond in JSON format with this exact structure:
{{
  "restaurants": [
    {{
      "name": "Restaurant Name",
      "description": "Brief description...",
      "cuisine_type": "Italian",
      "price_range": "$$$",
      "booking_website": "https://...",
      "source_rank": 4.5,
      "ranking_reason": "Featured as #3 on Essential 38 list with glowing review"
    }}
  ]
}}

If no restaurants meet the criteria, return {{"restaurants": []}}."""


def price_enrichment_prompt(
    restaurant_name: str,
    location: str,
    search_content: str
) -> str:
    """
    Generate prompt for extracting price tier from search results.

    Args:
        restaurant_name: Name of the restaurant
        location: City/region for context
        search_content: Combined search results content

    Returns:
        Formatted prompt string
    """
    return f"""Based on the following search results, determine the price range for {restaurant_name} in {location}.

SEARCH RESULTS:
{search_content[:4000]}

Price tiers (per person for dinner with one drink):
- $: Under $25
- $$: $25-50
- $$$: $50-100
- $$$$: Over $100

Look for:
- Menu prices or price ranges mentioned
- Descriptions like "fine dining", "casual", "upscale"
- Tasting menu prices (usually $$$$)
- Average check or cost per person mentions

Respond with ONLY the price tier symbol ($, $$, $$$, or $$$$).
If you cannot determine the price, respond with "unknown"."""
