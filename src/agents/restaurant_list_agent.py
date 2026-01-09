"""
RestaurantList Agent - LangGraph Implementation

Discovers new top restaurants and manages the curated restaurant list.
Based on RestaurantListAgent.md specification.
"""

import os
from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime

from rapidfuzz import fuzz

from langgraph.graph import StateGraph, END
from openai import OpenAI
from dotenv import load_dotenv

from models.restaurant import Restaurant, create_restaurant
from clients.google_sheets_client import GoogleSheetsClient
from utils.config import get_known_urls, get_search_queries, get_source_domains, get_deep_crawl_sources
from utils.cache import get_cached, set_cached, is_cache_enabled
from prompts import (
    restaurant_extraction_prompt,
    price_enrichment_prompt,
    priority_reasons_prompt,
    edit_command_prompt,
)
from prompts.extraction import RESTAURANT_EXTRACTION_SYSTEM, PRICE_ENRICHMENT_SYSTEM
from prompts.ranking import PRIORITY_REASONS_SYSTEM
from prompts.editing import EDIT_COMMAND_SYSTEM

# Load environment variables
load_dotenv()


# ============================================================================
# State Schema (Section 2.2)
# ============================================================================

class RestaurantListState(TypedDict):
    """State schema for RestaurantList Agent"""

    # User input
    user_message: str
    user_action: str  # "discover", "edit", "view"

    # Discovery process
    discovered_restaurants: List[Restaurant]
    search_results_raw: Dict[str, List[Restaurant]]  # source -> restaurants

    # Current state
    current_list: List[Restaurant]

    # Comparison results
    restaurants_to_add: List[Restaurant]
    restaurants_to_remove: List[Restaurant]

    # User interaction
    recommendation_message: str
    user_approval: Optional[bool]
    user_feedback: Optional[str]

    # Error handling
    errors: List[str]
    retry_count: int

    # Metadata
    last_discovery_date: Optional[datetime]


# ============================================================================
# Helper Functions
# ============================================================================

# Valid price range values
VALID_PRICE_RANGES = {'$', '$$', '$$$', '$$$$'}


def normalize_price_range(price: str) -> str:
    """
    Normalize and validate price range values.

    Handles common variants and extracts valid price ranges from
    malformed inputs like "$$$-$$$$", "$$$ - $$$$", "moderate", etc.

    Args:
        price: Raw price string from extraction

    Returns:
        Normalized price ('$', '$$', '$$$', '$$$$') or '' if invalid
    """
    if not price:
        return ''

    price = price.strip()

    # Direct match
    if price in VALID_PRICE_RANGES:
        return price

    # Handle ranges like "$$$-$$$$" or "$$$ - $$$$" - take the higher value
    if '-' in price or '–' in price:  # Handle both hyphen and en-dash
        # Extract all $ sequences
        import re
        matches = re.findall(r'\${1,4}', price)
        if matches:
            # Return the longest (most expensive) one
            return max(matches, key=len)

    # Handle "to" ranges like "$$$ to $$$$"
    if ' to ' in price.lower():
        import re
        matches = re.findall(r'\${1,4}', price)
        if matches:
            return max(matches, key=len)

    # Extract any valid price pattern from the string
    import re
    matches = re.findall(r'\${1,4}', price)
    if matches:
        # If multiple found, prefer the most common or longest
        return max(matches, key=len)

    # Handle word descriptions
    price_lower = price.lower()
    if any(word in price_lower for word in ['very expensive', 'fine dining', 'splurge', 'luxury']):
        return '$$$$'
    if any(word in price_lower for word in ['expensive', 'upscale', 'pricey']):
        return '$$$'
    if any(word in price_lower for word in ['moderate', 'mid-range', 'reasonable']):
        return '$$'
    if any(word in price_lower for word in ['cheap', 'budget', 'inexpensive', 'affordable']):
        return '$'

    # Unknown format
    return ''


def get_source_domain(source: str) -> str:
    """Map source names to their website domains from config."""
    return get_source_domains().get(source, "")


def find_matching_restaurant_key(name: str, by_name: Dict[str, Restaurant]) -> Optional[str]:
    """
    Find if a restaurant name matches any existing entry using fuzzy matching.

    Uses rapidfuzz to detect similar names like:
    - "Imperfecto" vs "Imperfecto: The Chef's Table"
    - "Sushi Nakazawa" vs "Sushi Nakazawa Washington DC"

    Args:
        name: Restaurant name to check
        by_name: Dict of existing restaurants keyed by lowercase name

    Returns:
        Matching key if found, None otherwise
    """
    name_lower = name.lower().strip()

    # Exact match first (fastest)
    if name_lower in by_name:
        return name_lower

    # Fuzzy match against all existing names
    for existing_name in by_name.keys():
        # Partial ratio catches substring matches
        # e.g., "Imperfecto" in "Imperfecto: The Chef's Table" → 100
        if fuzz.partial_ratio(name_lower, existing_name) >= 95:
            return existing_name

        # Token set ratio catches word reordering and extra words
        # e.g., "Sushi Nakazawa" vs "Sushi Nakazawa Washington DC" → 100
        if fuzz.token_set_ratio(name_lower, existing_name) >= 90:
            return existing_name

    return None


def merge_restaurant_data(existing: Restaurant, new: Restaurant) -> None:
    """
    Merge data from a duplicate restaurant into the existing entry.

    Prefers non-empty values and longer descriptions.

    Args:
        existing: The restaurant entry to update
        new: The duplicate restaurant with potentially useful data
    """
    # Merge string fields - prefer non-empty
    if not existing['description'] and new['description']:
        existing['description'] = new['description']
    elif new['description'] and len(new['description']) > len(existing['description']):
        # Prefer longer descriptions (more detail)
        existing['description'] = new['description']

    if not existing['price_range'] and new['price_range']:
        existing['price_range'] = new['price_range']

    if not existing['cuisine_type'] and new['cuisine_type']:
        existing['cuisine_type'] = new['cuisine_type']

    if not existing['booking_website'] and new['booking_website']:
        existing['booking_website'] = new['booking_website']

    # Merge source-specific rankings - take non-zero values
    if new.get('eater_dc_rank', 0) > 0 and existing.get('eater_dc_rank', 0) == 0:
        existing['eater_dc_rank'] = new['eater_dc_rank']

    if new.get('michelin_guide_rank', 0) > 0 and existing.get('michelin_guide_rank', 0) == 0:
        existing['michelin_guide_rank'] = new['michelin_guide_rank']

    if new.get('washington_post_rank', 0) > 0 and existing.get('washington_post_rank', 0) == 0:
        existing['washington_post_rank'] = new['washington_post_rank']

    if new.get('washingtonian_rank', 0) > 0 and existing.get('washingtonian_rank', 0) == 0:
        existing['washingtonian_rank'] = new['washingtonian_rank']

    if new.get('infatuation_rank', 0) > 0 and existing.get('infatuation_rank', 0) == 0:
        existing['infatuation_rank'] = new['infatuation_rank']


def deduplicate_restaurants(restaurants: List[Restaurant]) -> List[Restaurant]:
    """
    Deduplicate restaurants using fuzzy name matching, merging data from duplicates.

    Uses rapidfuzz to detect similar restaurant names that refer to the same place,
    such as:
    - "Imperfecto" vs "Imperfecto: The Chef's Table"
    - "Sushi Nakazawa" vs "Sushi Nakazawa Washington DC"

    When duplicates are found, data is merged, preferring non-empty values
    and longer descriptions.

    Args:
        restaurants: List of restaurants potentially with duplicates

    Returns:
        Deduplicated list with merged data
    """
    by_name: Dict[str, Restaurant] = {}

    for restaurant in restaurants:
        match_key = find_matching_restaurant_key(restaurant['name'], by_name)

        if match_key is None:
            # New restaurant - add it using lowercase name as key
            by_name[restaurant['name'].lower().strip()] = restaurant
        else:
            # Duplicate found - merge data
            merge_restaurant_data(by_name[match_key], restaurant)

    return list(by_name.values())


def extract_known_urls(tavily_client, location: str) -> Dict[str, List[Restaurant]]:
    """
    Extract restaurants directly from known high-value URLs.

    This guarantees we capture content from authoritative lists like
    Eater DC Heatmap and Essential 38, rather than hoping search finds them.

    Optimizations:
    - Caches Tavily API responses to avoid redundant calls
    - Batches content by source for fewer LLM calls
    - Parallelizes LLM extraction across sources

    Args:
        tavily_client: Initialized Tavily client
        location: City/region for filtering

    Returns:
        Dict mapping source name to list of extracted restaurants
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results_by_source = {}

    # Collect all URLs with their source names
    url_to_source = {}
    all_urls = []
    known_urls = get_known_urls()
    for source, urls in known_urls.items():
        for url in urls:
            url_to_source[url] = source
            all_urls.append(url)

    if not all_urls:
        return results_by_source

    print(f"\n  Extracting {len(all_urls)} known high-value URLs...")

    # Track content by source for batching LLM calls
    source_contents = {}  # source -> list of (url, content)
    successful_urls = set()

    # Strategy 1: Use Tavily extract (fast, but may miss dynamic content)
    # Check cache first for each URL
    urls_to_fetch = []
    for url in all_urls:
        cached_content = get_cached(url, 'extract')
        if cached_content:
            source = url_to_source[url]
            if source not in source_contents:
                source_contents[source] = []
            source_contents[source].append((url, cached_content))
            print(f"    [cache] {source}: Using cached content for {url[:50]}...")
        else:
            urls_to_fetch.append(url)

    # Fetch uncached URLs
    if urls_to_fetch:
        try:
            extract_result = tavily_client.extract(urls=urls_to_fetch)

            for item in extract_result.get('results', []):
                url = item.get('url', '')
                raw_content = item.get('raw_content', '')

                if not raw_content or url not in url_to_source:
                    continue

                source = url_to_source[url]

                # Cache the result
                set_cached(url, raw_content, 'extract')

                # Add to source contents for batched LLM processing
                if source not in source_contents:
                    source_contents[source] = []
                source_contents[source].append((url, raw_content))

                # Mark as successful if we got content
                if len(raw_content) >= 1000:
                    successful_urls.add(url)

        except Exception as e:
            print(f"    ✗ Error with extract: {e}")

    # Strategy 2: Use Tavily crawl for URLs that yielded little/no content
    urls_to_crawl = [url for url in all_urls if url not in successful_urls and url not in [u for contents in source_contents.values() for u, _ in contents]]

    if urls_to_crawl:
        print(f"\n  Crawling {len(urls_to_crawl)} URLs for more complete extraction...")

        for url in urls_to_crawl:
            source = url_to_source[url]

            # Check cache first
            cached_content = get_cached(url, 'crawl')
            if cached_content:
                if source not in source_contents:
                    source_contents[source] = []
                source_contents[source].append((url, cached_content))
                print(f"    [cache] {source}: Using cached crawl for {url[:50]}...")
                continue

            try:
                crawl_result = tavily_client.crawl(
                    url=url,
                    max_depth=1,
                    max_breadth=1,
                    limit=1
                )

                all_content = []
                for page in crawl_result.get('results', []):
                    content = page.get('raw_content', '') or page.get('content', '')
                    if content:
                        all_content.append(content)

                combined_content = "\n\n---\n\n".join(all_content)

                if combined_content:
                    # Cache the result
                    set_cached(url, combined_content, 'crawl')

                    if source not in source_contents:
                        source_contents[source] = []
                    source_contents[source].append((url, combined_content))

            except Exception as e:
                print(f"    ✗ Error crawling {url}: {e}")

    # Batch LLM calls by source and run in parallel
    # Combine all content from same source into single LLM call
    def process_source(source: str, contents: List[tuple]) -> tuple:
        """Process all URLs for a single source with one LLM call."""
        try:
            # Combine content from all URLs for this source
            combined_parts = []
            for url, content in contents:
                combined_parts.append(f"=== Content from {url} ===\n\n{content}")

            combined_content = "\n\n---PAGE BREAK---\n\n".join(combined_parts)
            total_chars = len(combined_content)

            restaurants = llm_extract_restaurants(
                source=f"{source} (direct)",
                search_results=combined_content,
                location=location
            )

            return source, restaurants, total_chars, None
        except Exception as e:
            return source, [], 0, str(e)

    # Process sources in parallel
    print(f"\n  Processing {len(source_contents)} sources with LLM (parallel)...")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_source, source, contents): source
            for source, contents in source_contents.items()
        }

        for future in as_completed(futures):
            source, restaurants, char_count, error = future.result()

            if error:
                print(f"    ✗ {source}: Error - {error}")
            else:
                results_by_source[source] = restaurants
                url_count = len(source_contents.get(source, []))
                print(f"    ✓ {source}: Extracted {len(restaurants)} restaurants from {url_count} URLs ({char_count:,} chars)")

    return results_by_source


def extract_deep_crawl_sources(tavily_client, location: str) -> Dict[str, List[Restaurant]]:
    """
    Extract restaurants from sources that require deep crawling.

    For sources like Michelin Guide where the list page only shows names,
    but detailed info is on individual restaurant pages, this function:
    1. Crawls the list page to discover restaurant URLs
    2. Filters URLs matching the restaurant pattern
    3. Extracts content from individual restaurant pages
    4. Parses restaurant details from each page

    Optimizations:
    - Caches map and extract results to avoid redundant API calls
    - Processes batches in parallel where possible

    Args:
        tavily_client: Initialized Tavily client
        location: City/region for filtering

    Returns:
        Dict mapping source name to list of extracted restaurants
    """
    import re
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results_by_source = {}
    deep_crawl_sources = get_deep_crawl_sources()

    if not deep_crawl_sources:
        return results_by_source

    print(f"\n  Deep crawling {len(deep_crawl_sources)} sources for individual restaurant pages...")

    for source, config in deep_crawl_sources.items():
        list_url = config.get('list_url')
        url_pattern = config.get('restaurant_url_pattern', '.*')
        max_restaurants = config.get('max_restaurants', 30)

        if not list_url:
            continue

        print(f"\n    [{source}] Discovering restaurant URLs from {list_url}...")

        try:
            # Step 1: Map the list page to discover all links (with caching)
            cached_urls = get_cached(list_url, 'map')
            if cached_urls:
                all_urls = cached_urls
                print(f"    [{source}] Using cached map results ({len(all_urls)} URLs)")
            else:
                map_result = tavily_client.map(
                    url=list_url,
                    max_depth=2,
                    max_breadth=100,
                    limit=300
                )
                all_urls = map_result.get('results', [])
                set_cached(list_url, all_urls, 'map')

            # Step 2: Filter URLs matching restaurant pattern
            pattern = re.compile(url_pattern)
            restaurant_urls = [url for url in all_urls if pattern.search(url)]

            # Deduplicate and limit
            restaurant_urls = list(dict.fromkeys(restaurant_urls))[:max_restaurants]

            print(f"    [{source}] Found {len(restaurant_urls)} restaurant pages (from {len(all_urls)} total links)")

            if not restaurant_urls:
                continue

            # Step 3: Extract content from individual restaurant pages
            # Check cache first, then fetch missing URLs
            all_content = []
            urls_to_fetch = []

            for url in restaurant_urls:
                cached_content = get_cached(url, 'extract')
                if cached_content:
                    all_content.append(cached_content)
                else:
                    urls_to_fetch.append(url)

            if all_content:
                print(f"    [{source}] Using {len(all_content)} cached pages")

            # Fetch uncached URLs in batches (parallel batches)
            if urls_to_fetch:
                batch_size = 10
                batches = [urls_to_fetch[i:i + batch_size] for i in range(0, len(urls_to_fetch), batch_size)]

                def fetch_batch(batch_urls):
                    """Fetch a batch of URLs."""
                    batch_content = []
                    try:
                        extract_result = tavily_client.extract(urls=batch_urls)
                        for item in extract_result.get('results', []):
                            url = item.get('url', '')
                            content = item.get('raw_content', '')
                            if content:
                                set_cached(url, content, 'extract')
                                batch_content.append(content)
                    except Exception as e:
                        print(f"    [{source}] Error extracting batch: {e}")
                    return batch_content

                # Process batches in parallel
                print(f"    [{source}] Fetching {len(urls_to_fetch)} pages in {len(batches)} batches (parallel)...")

                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = [executor.submit(fetch_batch, batch) for batch in batches]
                    for future in as_completed(futures):
                        batch_content = future.result()
                        all_content.extend(batch_content)

            # Step 4: Combine all content and extract restaurants
            if all_content:
                combined_content = "\n\n---RESTAURANT PAGE---\n\n".join(all_content)
                print(f"    [{source}] Parsing {len(all_content)} restaurant pages ({len(combined_content):,} chars)...")

                restaurants = llm_extract_restaurants(
                    source=f"{source} (deep)",
                    search_results=combined_content,
                    location=location
                )

                results_by_source[source] = restaurants
                print(f"    ✓ {source}: Extracted {len(restaurants)} restaurants from {len(all_content)} pages")

        except Exception as e:
            print(f"    ✗ {source}: Error during deep crawl: {e}")

    return results_by_source


def map_source_to_rank_field(source: str) -> str:
    """
    Map a source name to its corresponding rank field in the Restaurant model.

    Args:
        source: Source name (may include suffixes like "(direct)" or "(deep)")

    Returns:
        Field name (e.g., "eater_dc_rank") or empty string if not recognized
    """
    # Normalize source name by removing suffixes
    source_base = source.replace(" (direct)", "").replace(" (deep)", "").strip().lower()

    if "eater" in source_base:
        return "eater_dc_rank"
    elif "michelin" in source_base:
        return "michelin_guide_rank"
    elif "washington post" in source_base:
        return "washington_post_rank"
    elif "washingtonian" in source_base:
        return "washingtonian_rank"
    elif "infatuation" in source_base:
        return "infatuation_rank"
    else:
        return ""


def llm_extract_restaurants(
    source: str,
    search_results: str,
    location: str
) -> List[Restaurant]:
    """
    Use LLM to parse search results, extract restaurant details, AND rank them.

    Now combines extraction and ranking in a single LLM call so the ranking
    has full context of how each restaurant is featured in the source
    (position in list, prominence, language used).

    Handles large content by processing in chunks if necessary.

    Args:
        source: Name of authoritative source
        search_results: Raw search results text
        location: City/region to filter by

    Returns:
        List of Restaurant dictionaries with source-specific rankings populated
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # For large content (like Eater heatmap with 30+ restaurants), process in chunks
    # GPT-4o-mini can handle ~128k tokens, but we chunk at 50k chars for efficiency
    MAX_CHUNK_SIZE = 50000
    all_restaurants = []

    # Determine which rank field this source maps to
    rank_field = map_source_to_rank_field(source)

    # Split content into chunks if needed
    if len(search_results) > MAX_CHUNK_SIZE:
        chunks = []
        for i in range(0, len(search_results), MAX_CHUNK_SIZE):
            chunks.append(search_results[i:i + MAX_CHUNK_SIZE])
    else:
        chunks = [search_results]

    for chunk_idx, chunk in enumerate(chunks):
        chunk_label = f" (chunk {chunk_idx + 1}/{len(chunks)})" if len(chunks) > 1 else ""

        system_prompt = RESTAURANT_EXTRACTION_SYSTEM
        user_prompt = restaurant_extraction_prompt(
            source=source,
            location=location,
            content=chunk,
            chunk_label=chunk_label
        )

        try:
            response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            # Convert to Restaurant TypedDict format and add to aggregate list
            for r in result.get('restaurants', []):
                # Normalize price range to handle variants
                raw_price = r.get('price_range', '')
                normalized_price = normalize_price_range(raw_price)

                # Get the source rank from extraction (now included in response)
                source_rank = float(r.get('source_rank', 0.0))
                ranking_reason = r.get('ranking_reason', '')

                # Build kwargs for source-specific rank field
                rank_kwargs = {}
                if rank_field and source_rank > 0:
                    rank_kwargs[rank_field] = source_rank

                all_restaurants.append(create_restaurant(
                    name=r.get('name', ''),
                    booking_website=r.get('booking_website', ''),
                    description=r.get('description', ''),
                    price_range=normalized_price,
                    cuisine_type=r.get('cuisine_type', ''),
                    priority_rank=0.0,  # Will be aggregated later from source ranks
                    priority_reasons=ranking_reason,  # Store the ranking reason for now
                    **rank_kwargs
                ))

        except Exception as e:
            print(f"Error extracting restaurants from {source}{chunk_label}: {e}")

    # Deduplicate restaurants across chunks (same restaurant might appear in overlapping content)
    return deduplicate_restaurants(all_restaurants)


def llm_generate_priority_reasons(
    restaurant: Restaurant,
    source_rankings: Dict[str, float]
) -> str:
    """
    Generate 1-3 sentences explaining why this restaurant is prioritized.

    Args:
        restaurant: Restaurant to explain
        source_rankings: Dict of source name -> ranking

    Returns:
        Priority reasons string
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    rankings_text = "\n".join([f"- {source}: {rank}/5.0" for source, rank in source_rankings.items()])

    system_prompt = PRIORITY_REASONS_SYSTEM
    user_prompt = priority_reasons_prompt(
        restaurant_name=restaurant['name'],
        description=restaurant['description'],
        priority_rank=restaurant['priority_rank'],
        rankings_text=rankings_text
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error generating priority reasons: {e}")
        return "Featured in multiple authoritative DC food sources."


def llm_parse_edit_command(user_message: str) -> Dict[str, Any]:
    """
    Use LLM to parse natural language edit commands.

    Args:
        user_message: User's edit command

    Returns:
        Dict with action, restaurant_name, field, new_value
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    system_prompt = EDIT_COMMAND_SYSTEM
    user_prompt = edit_command_prompt(user_message)

    try:
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )

        import json
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"Error parsing edit command: {e}")
        return {"action": "unknown", "restaurant_name": "", "field": None, "new_value": None}


def find_restaurant_by_name(restaurants: List[Restaurant], name: str) -> Optional[Restaurant]:
    """Find a restaurant in list by name (case-insensitive)."""
    name_lower = name.lower()
    for restaurant in restaurants:
        if restaurant['name'].lower() == name_lower:
            return restaurant
    return None


def enrich_missing_prices(
    restaurants: List[Restaurant],
    tavily_client,
    location: str
) -> List[Restaurant]:
    """
    Enrich restaurants that have missing price ranges by searching for price info.

    Uses Tavily to search for price information and LLM to extract the price tier.
    Processes restaurants in parallel for efficiency.

    Args:
        restaurants: List of restaurants, some potentially missing price_range
        tavily_client: Initialized Tavily client
        location: City/region for search context

    Returns:
        Same list with price_range filled in where possible
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Find restaurants missing prices
    missing_prices = [r for r in restaurants if not r.get('price_range')]

    if not missing_prices:
        return restaurants

    print(f"\n  Enriching prices for {len(missing_prices)} restaurants with missing price data...")

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def enrich_single_restaurant(restaurant: Restaurant) -> tuple:
        """Search for and extract price for a single restaurant."""
        name = restaurant['name']

        # Check cache first
        cache_key = f"price:{name}|{location}"
        cached_price = get_cached(cache_key, 'price')
        if cached_price:
            return name, cached_price, "cache"

        try:
            # Search for price information
            search_query = f"{name} {location} restaurant price cost per person menu"
            search_result = tavily_client.search(
                query=search_query,
                search_depth="basic",
                max_results=3,
                include_raw_content=True
            )

            # Combine search results
            content_parts = []
            for result in search_result.get('results', []):
                snippet = result.get('content', '')
                raw = result.get('raw_content', '')
                if raw:
                    content_parts.append(raw[:2000])  # Limit content size
                elif snippet:
                    content_parts.append(snippet)

            if not content_parts:
                return name, '', "no results"

            combined_content = "\n\n".join(content_parts)

            # Use LLM to extract price
            system_prompt = PRICE_ENRICHMENT_SYSTEM
            user_prompt = price_enrichment_prompt(
                restaurant_name=name,
                location=location,
                search_content=combined_content
            )

            response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=10
            )

            raw_price = response.choices[0].message.content.strip() if response.choices[0].message.content else ''
            normalized_price = normalize_price_range(raw_price)

            # Cache the result (even if empty, to avoid repeated lookups)
            set_cached(cache_key, normalized_price, 'price')

            return name, normalized_price, "searched"

        except Exception as e:
            return name, '', f"error: {e}"

    # Process in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(enrich_single_restaurant, r): r
            for r in missing_prices
        }

        for future in as_completed(futures):
            name, price, source = future.result()
            results[name.lower()] = price
            status = f"→ {price}" if price else "→ unknown"
            print(f"    {name}: {status} ({source})")

    # Update restaurants with enriched prices
    enriched_count = 0
    for restaurant in restaurants:
        if not restaurant.get('price_range'):
            enriched_price = results.get(restaurant['name'].lower(), '')
            if enriched_price:
                restaurant['price_range'] = enriched_price
                enriched_count += 1

    print(f"  Enriched {enriched_count}/{len(missing_prices)} restaurants with price data\n")

    return restaurants


# ============================================================================
# Graph Nodes (Section 4)
# ============================================================================

def initiate_discovery(state: RestaurantListState) -> RestaurantListState:
    """
    Parse user request and initialize discovery process.
    """
    user_message = state['user_message'].lower()

    # Determine user action
    if any(keyword in user_message for keyword in ['find', 'discover', 'search', 'new', 'update']):
        state['user_action'] = 'discover'
    elif any(keyword in user_message for keyword in ['remove', 'delete', 'edit', 'change']):
        state['user_action'] = 'edit'
    elif any(keyword in user_message for keyword in ['show', 'view', 'list']):
        state['user_action'] = 'view'
    else:
        state['user_action'] = 'discover'  # Default

    # Initialize discovery fields
    state['discovered_restaurants'] = []
    state['search_results_raw'] = {}
    state['restaurants_to_add'] = []
    state['restaurants_to_remove'] = []
    state['errors'] = []

    return state


def run_source_search(tavily_client, location: str, sources: List[str]) -> Dict[str, List[Restaurant]]:
    """
    Run source-specific search queries in parallel.

    Strategy 2: Uses tailored search queries for each source.
    Includes caching for search results.

    Args:
        tavily_client: Initialized Tavily client
        location: City/region for filtering
        sources: List of source names to search

    Returns:
        Dict mapping source name to list of restaurants
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results_by_source = {}

    def search_single_source(source: str) -> tuple:
        """Search a single source using source-specific queries."""
        try:
            source_domain = get_source_domain(source)
            search_queries_config = get_search_queries()
            queries = search_queries_config.get(source, [f"best restaurants {location}"])

            source_restaurants = []

            for query in queries:
                # Create cache key from query + domain
                cache_key = f"{query}|{source_domain or 'all'}"

                # Check cache first
                cached_results = get_cached(cache_key, 'search')
                if cached_results:
                    content_snippets = cached_results
                else:
                    search_params = {
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 5,
                        "include_raw_content": True
                    }

                    if source_domain:
                        search_params["include_domains"] = [source_domain]

                    search_results = tavily_client.search(**search_params)

                    # Extract content snippets
                    content_snippets = []
                    for result in search_results.get('results', []):
                        raw = result.get('raw_content', '')
                        snippet = result.get('content', '')
                        content = raw if raw else snippet
                        if content:
                            content_snippets.append(content)

                    # Cache the content snippets
                    set_cached(cache_key, content_snippets, 'search')

                combined_content = "\n\n".join(content_snippets)

                if combined_content:
                    restaurants = llm_extract_restaurants(
                        source=source,
                        search_results=combined_content,
                        location=location
                    )
                    source_restaurants.extend(restaurants)

            # Deduplicate within this source
            unique_source_restaurants = deduplicate_restaurants(source_restaurants)
            return source, unique_source_restaurants, None

        except Exception as e:
            return source, [], str(e)

    # Execute searches in parallel
    print(f"  Searching {len(sources)} sources with tailored queries (parallel)...")

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_source = {
            executor.submit(search_single_source, source): source
            for source in sources
        }

        for i, future in enumerate(as_completed(future_to_source), 1):
            source, restaurants, error = future.result()

            if error:
                print(f"    [{i}/{len(sources)}] ✗ {source}: {error}")
            else:
                print(f"    [{i}/{len(sources)}] ✓ {source}: Found {len(restaurants)} restaurants")
                results_by_source[source] = restaurants

    return results_by_source


def search_sources(state: RestaurantListState) -> RestaurantListState:
    """
    Search authoritative sources for new restaurants using Tavily API.

    Uses three strategies for comprehensive coverage, running in PARALLEL:
    1. Direct extraction from known high-value URLs (guaranteed capture)
    2. Source-specific search queries (better matching to article titles)
    3. Deep crawl for sources with individual restaurant pages (e.g., Michelin Guide)

    Optimizations:
    - All 3 strategies run in parallel for 2-3x speedup
    - Each strategy uses internal parallelization and caching
    """
    from tavily import TavilyClient
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    start_time = time.time()

    location = os.getenv('LOCATION_CITY', 'Washington DC')
    tavily_api_key = os.getenv('TAVILY_API_KEY')

    if not tavily_api_key:
        state['errors'].append("TAVILY_API_KEY not found in .env file")
        print("Error: TAVILY_API_KEY not set. Please add it to your .env file.")
        return state

    # Authoritative sources for Strategy 2
    sources = [
        "Eater DC",
        "Michelin Guide",
        "Washington Post Food",
        "Washingtonian Magazine",
        "Infatuation"
    ]

    try:
        tavily_client = TavilyClient(api_key=tavily_api_key)
    except Exception as e:
        state['errors'].append(f"Failed to initialize Tavily client: {str(e)}")
        print(f"Error initializing Tavily: {e}")
        return state

    cache_status = "enabled" if is_cache_enabled() else "disabled"
    print(f"\nSearching for restaurants in {location}... (cache: {cache_status})")
    print("Running all 3 strategies in PARALLEL for faster results...\n")

    # =========================================================================
    # Run all 3 strategies in PARALLEL
    # =========================================================================
    all_discovered = []
    results_by_source = {}
    strategy_results = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all 3 strategies
        future_strategy1 = executor.submit(extract_known_urls, tavily_client, location)
        future_strategy2 = executor.submit(run_source_search, tavily_client, location, sources)
        future_strategy3 = executor.submit(extract_deep_crawl_sources, tavily_client, location)

        futures = {
            future_strategy1: "Strategy 1 (Known URLs)",
            future_strategy2: "Strategy 2 (Source Search)",
            future_strategy3: "Strategy 3 (Deep Crawl)"
        }

        # Collect results as they complete
        for future in as_completed(futures):
            strategy_name = futures[future]
            try:
                result = future.result()
                strategy_results[strategy_name] = result

                # Count restaurants
                count = sum(len(r) for r in result.values())
                print(f"[DONE] {strategy_name}: {count} restaurants from {len(result)} sources")

            except Exception as e:
                print(f"[ERROR] {strategy_name}: {e}")
                state['errors'].append(f"{strategy_name} failed: {str(e)}")

    # =========================================================================
    # Combine results from all strategies
    # =========================================================================
    print("\nCombining results from all strategies...")

    for strategy_name, result in strategy_results.items():
        for source, restaurants in result.items():
            if source not in results_by_source:
                results_by_source[source] = []
            results_by_source[source].extend(restaurants)
            all_discovered.extend(restaurants)

    # =========================================================================
    # Deduplicate all results
    # =========================================================================
    unique_restaurants = deduplicate_restaurants(all_discovered)

    elapsed_time = time.time() - start_time
    print(f"\nTotal restaurants found: {len(all_discovered)}")
    print(f"Unique restaurants after deduplication: {len(unique_restaurants)}")
    print(f"Search completed in {elapsed_time:.1f} seconds\n")

    state['discovered_restaurants'] = unique_restaurants
    state['search_results_raw'] = results_by_source

    return state


def evaluate_restaurants(state: RestaurantListState) -> RestaurantListState:
    """
    Aggregate source rankings and generate priority reasons.

    Source rankings are now populated during extraction (combined extraction+ranking),
    so this function just aggregates them into an overall priority_rank and
    generates the final priority_reasons text.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print("Aggregating rankings and generating priority reasons...")

    def aggregate_and_generate_reasons(restaurant: Restaurant) -> Restaurant:
        """Aggregate source rankings and generate priority reasons for one restaurant."""
        # Collect all non-zero source rankings
        source_rankings = {}
        if restaurant.get('eater_dc_rank', 0) > 0:
            source_rankings['Eater DC'] = restaurant['eater_dc_rank']
        if restaurant.get('michelin_guide_rank', 0) > 0:
            source_rankings['Michelin Guide'] = restaurant['michelin_guide_rank']
        if restaurant.get('washington_post_rank', 0) > 0:
            source_rankings['Washington Post'] = restaurant['washington_post_rank']
        if restaurant.get('washingtonian_rank', 0) > 0:
            source_rankings['Washingtonian'] = restaurant['washingtonian_rank']
        if restaurant.get('infatuation_rank', 0) > 0:
            source_rankings['Infatuation'] = restaurant['infatuation_rank']

        # Calculate overall priority rank (average of source rankings)
        if source_rankings:
            overall_rank = sum(source_rankings.values()) / len(source_rankings)
            restaurant['priority_rank'] = round(overall_rank, 1)

            # Generate priority reasons (LLM call to synthesize a compelling summary)
            restaurant['priority_reasons'] = llm_generate_priority_reasons(
                restaurant=restaurant,
                source_rankings=source_rankings
            )

            # Print rankings
            sources_str = ", ".join([f"{s}={r}" for s, r in source_rankings.items()])
            print(f"  ✓ {restaurant['name']}: {sources_str} → avg {restaurant['priority_rank']}/5.0")
        else:
            restaurant['priority_rank'] = 0.0
            if not restaurant.get('priority_reasons'):
                restaurant['priority_reasons'] = "No source rankings available"
            print(f"  ✗ {restaurant['name']}: No source rankings")

        return restaurant

    # Process all restaurants in parallel (for priority reasons generation)
    evaluated_restaurants = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_restaurant = {
            executor.submit(aggregate_and_generate_reasons, restaurant): restaurant
            for restaurant in state['discovered_restaurants']
        }

        for future in as_completed(future_to_restaurant):
            try:
                evaluated_restaurant = future.result()
                evaluated_restaurants.append(evaluated_restaurant)
            except Exception as e:
                restaurant = future_to_restaurant[future]
                print(f"  ✗ Error evaluating {restaurant['name']}: {e}")
                restaurant['priority_rank'] = 0.0
                restaurant['priority_reasons'] = "Evaluation failed"
                evaluated_restaurants.append(restaurant)

    # Enrich missing prices before filtering
    missing_price_count = sum(1 for r in evaluated_restaurants if not r.get('price_range'))
    if missing_price_count > 0:
        try:
            from tavily import TavilyClient
            tavily_api_key = os.getenv('TAVILY_API_KEY')
            if tavily_api_key:
                tavily_client = TavilyClient(api_key=tavily_api_key)
                location = os.getenv('LOCATION_CITY', 'Washington DC')
                evaluated_restaurants = enrich_missing_prices(
                    evaluated_restaurants,
                    tavily_client,
                    location
                )
        except Exception as e:
            print(f"  Warning: Price enrichment failed: {e}")

    # Filter out low priority restaurants (below 2.0)
    filtered = [
        r for r in evaluated_restaurants
        if r['priority_rank'] >= 2.0
    ]

    print(f"\nRestaurants after filtering (>= 2.0 priority): {len(filtered)}/{len(evaluated_restaurants)}\n")

    state['discovered_restaurants'] = filtered

    return state


def fetch_current_list(state: RestaurantListState) -> RestaurantListState:
    """
    Retrieve existing restaurant list from Google Sheets.
    """
    try:
        sheets_client = GoogleSheetsClient()
        current_list = sheets_client.get_all_restaurants()
        state['current_list'] = current_list
    except Exception as e:
        state['errors'].append(f"Failed to fetch current list: {str(e)}")
        state['current_list'] = []

    return state


def compare_lists(state: RestaurantListState) -> RestaurantListState:
    """
    Compare discovered restaurants against current list.
    Identify new restaurants to add.
    """
    current_names = {r['name'].lower() for r in state['current_list']}

    # Additions: in discovered but not in current
    state['restaurants_to_add'] = [
        r for r in state['discovered_restaurants']
        if r['name'].lower() not in current_names
    ]

    # Removals: Not implemented in MVP (manual removal via conversational editing)
    state['restaurants_to_remove'] = []

    return state


def present_recommendations(state: RestaurantListState) -> RestaurantListState:
    """
    Format and present recommended additions to user.
    """
    num_additions = len(state['restaurants_to_add'])

    if num_additions == 0:
        state['recommendation_message'] = "I didn't find any new restaurants to add. Your list is up to date!"
        return state

    # Build recommendation message
    message = f"I found {num_additions} new restaurant{'s' if num_additions > 1 else ''} for your list:\n\n"
    message += "NEW RESTAURANTS:\n"

    for i, restaurant in enumerate(state['restaurants_to_add'], 1):
        message += f"\n{i}. **{restaurant['name']}**\n"
        message += f"   Description: {restaurant['description']}\n"
        message += f"   Overall Priority Rank: {restaurant['priority_rank']}/5.0\n"
        message += f"   Priority Reasons: {restaurant['priority_reasons']}\n"
        message += f"   Cuisine: {restaurant['cuisine_type']} | Price: {restaurant['price_range']}\n"

    message += "\n\nWould you like to add these restaurants to your list?"

    state['recommendation_message'] = message
    return state


def await_user_approval(state: RestaurantListState) -> RestaurantListState:
    """
    Interrupt the graph and wait for user input.
    This node doesn't modify state - LangGraph handles the interrupt.
    """
    return state


def update_google_sheet(state: RestaurantListState) -> RestaurantListState:
    """
    Add approved restaurants to Google Sheets using batch insert to avoid rate limits.
    """
    import sys
    print("\n" + "="*60, flush=True)
    print("UPDATE_GOOGLE_SHEET FUNCTION CALLED", flush=True)
    print("="*60, flush=True)
    print(f"[DEBUG] Attempting to add {len(state['restaurants_to_add'])} restaurants to Google Sheets...", flush=True)
    print(f"[DEBUG] User approval status: {state.get('user_approval')}", flush=True)
    sys.stdout.flush()

    try:
        sheets_client = GoogleSheetsClient()
        print("[DEBUG] Google Sheets client initialized", flush=True)

        # Convert Restaurant TypedDicts to plain dicts for compatibility
        restaurants_to_add = [dict(r) for r in state['restaurants_to_add']]

        # Use batch insert (single API call) to avoid rate limits
        print(f"[DEBUG] Adding {len(restaurants_to_add)} restaurants in single batch...", flush=True)
        sheets_client.add_multiple_restaurants(restaurants_to_add)

        # Update last discovery date
        state['last_discovery_date'] = datetime.now()

        print(f"\n✅ Successfully added {len(restaurants_to_add)} restaurants to Google Sheets\n", flush=True)

    except Exception as e:
        error_msg = f"Failed to initialize Google Sheets: {str(e)}"
        print(f"\n❌ ERROR: {error_msg}\n", flush=True)
        state['errors'].append(error_msg)
        import traceback
        traceback.print_exc()

    return state


def handle_conversational_edit(state: RestaurantListState) -> RestaurantListState:
    """
    Parse natural language edit commands and prepare state for approval.
    """
    user_message = state['user_message']

    # Use LLM to parse edit intent
    edit_intent = llm_parse_edit_command(user_message)

    if edit_intent['action'] == 'remove':
        # Find restaurant in current list
        restaurant = find_restaurant_by_name(
            state['current_list'],
            edit_intent['restaurant_name']
        )
        if restaurant:
            state['restaurants_to_remove'] = [restaurant]
            state['recommendation_message'] = f"Remove {restaurant['name']} from your list?"
        else:
            state['recommendation_message'] = f"I couldn't find '{edit_intent['restaurant_name']}' in your list."

    elif edit_intent['action'] == 'update':
        state['recommendation_message'] = "Update functionality not yet implemented in MVP."

    elif edit_intent['action'] == 'add':
        state['recommendation_message'] = "Manual add functionality not yet implemented in MVP."

    else:
        state['recommendation_message'] = "I didn't understand that command. Try 'Remove [Restaurant Name]' or 'Find new restaurants'."

    return state


def error_handler(state: RestaurantListState) -> RestaurantListState:
    """
    Handle errors and present to user with retry option.
    """
    errors_list = "\n".join(state['errors'])

    error_message = f"""I encountered an error during restaurant discovery.

**What happened:** The discovery process failed.

**Technical Details:**
{errors_list}

Would you like me to try again or cancel this discovery?"""

    state['recommendation_message'] = error_message
    return state


# ============================================================================
# Conditional Routing
# ============================================================================

def route_after_approval(state: RestaurantListState) -> str:
    """
    Route to update_google_sheet if approved, otherwise END.
    """
    if state.get('user_approval') == True:
        return "update_google_sheet"
    else:
        return END


def route_after_initiate(state: RestaurantListState) -> str:
    """
    Route based on user action.
    """
    action = state.get('user_action', 'discover')

    if action == 'edit':
        return "handle_conversational_edit"
    elif action == 'view':
        return "fetch_current_list"
    else:  # discover
        return "search_sources"


# ============================================================================
# Build Graph
# ============================================================================

def build_restaurant_list_graph() -> StateGraph:
    """
    Build the RestaurantList agent LangGraph.

    Returns:
        Compiled StateGraph
    """
    # Create graph
    graph = StateGraph(RestaurantListState)

    # Add nodes
    graph.add_node("initiate_discovery", initiate_discovery)
    graph.add_node("search_sources", search_sources)
    graph.add_node("evaluate_restaurants", evaluate_restaurants)
    graph.add_node("fetch_current_list", fetch_current_list)
    graph.add_node("compare_lists", compare_lists)
    graph.add_node("present_recommendations", present_recommendations)
    graph.add_node("await_user_approval", await_user_approval)
    graph.add_node("update_google_sheet", update_google_sheet)
    graph.add_node("handle_conversational_edit", handle_conversational_edit)
    graph.add_node("error_handler", error_handler)

    # Add edges
    graph.set_entry_point("initiate_discovery")

    # Conditional routing after initiate
    graph.add_conditional_edges(
        "initiate_discovery",
        route_after_initiate,
        {
            "search_sources": "search_sources",
            "handle_conversational_edit": "handle_conversational_edit",
            "fetch_current_list": "fetch_current_list"
        }
    )

    # Discovery flow
    graph.add_edge("search_sources", "evaluate_restaurants")
    graph.add_edge("evaluate_restaurants", "fetch_current_list")
    graph.add_edge("fetch_current_list", "compare_lists")
    graph.add_edge("compare_lists", "present_recommendations")
    graph.add_edge("present_recommendations", "await_user_approval")

    # Conditional routing after approval
    graph.add_conditional_edges(
        "await_user_approval",
        route_after_approval,
        {
            "update_google_sheet": "update_google_sheet",
            END: END
        }
    )

    graph.add_edge("update_google_sheet", END)

    # Edit flow
    graph.add_edge("handle_conversational_edit", "await_user_approval")

    # Error handling
    graph.add_edge("error_handler", "present_recommendations")

    return graph
