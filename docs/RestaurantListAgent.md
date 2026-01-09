# RestaurantList Agent - Technical Specification

**Agent Name:** RestaurantList Agent
**Purpose:** Discover new upscale restaurants and manage the curated restaurant list
**User Stories:** US-1 (Discover new restaurants), US-2 (Manage my restaurant list)
**Version:** 1.0
**Last Updated:** 2025-12-31
**Status:** Draft

---

## 1. Overview

### 1.1 Agent Responsibilities
The RestaurantList Agent is responsible for:
1. **Discovery**: Searching authoritative sources for new upscale DC-area restaurants
2. **Evaluation**: Scoring restaurants based on defined criteria and assigning priority ranks
3. **Comparison**: Identifying additions/removals by comparing discoveries against the existing list
4. **User Interaction**: Presenting recommendations and gathering user approval
5. **Persistence**: Updating the Google Sheets restaurant list after user confirmation

### 1.2 Integration Points
- **Input**: User requests via chat interface ("Find new restaurants", "Update restaurant list")
- **Output**: Google Sheets updates, conversational responses
- **External APIs**: Web search, Yelp API, Google Sheets API
- **LLM**: OpenAI gpt-5-mini for decision-making and evaluation

---

## 2. LangGraph Agent Design

### 2.1 Graph Structure

**Graph Type:** StateGraph
**State Schema:** `RestaurantListState` (defined in section 2.2)

**Nodes:**
1. `initiate_discovery` - Parse user request and initialize discovery process
2. `search_sources` - Search authoritative restaurant sources using Tavily AI
3. `evaluate_restaurants` - Score and rank restaurants (1.0-5.0 per source, then average)
4. `fetch_current_list` - Retrieve existing restaurant list from Google Sheets
5. `compare_lists` - Identify additions by comparing against current list
6. `present_recommendations` - Format and present recommendations to user
7. `await_user_approval` - Wait for user confirmation (interrupt point)
8. `update_google_sheet` - Apply approved changes to Google Sheets
9. `handle_conversational_edit` - Process ad-hoc user edits ("Remove Restaurant X")
10. `error_handler` - Handle and retry failures

**Edges:**
```
START → initiate_discovery
initiate_discovery → search_sources
search_sources → evaluate_restaurants
evaluate_restaurants → fetch_current_list
fetch_current_list → compare_lists
compare_lists → present_recommendations
present_recommendations → await_user_approval (interrupt)
await_user_approval → [update_google_sheet | END] (conditional based on approval)
update_google_sheet → END

handle_conversational_edit → await_user_approval
error_handler → [retry | present_recommendations with error message]
```

### 2.2 State Schema

```python
from typing import TypedDict, List, Optional
from datetime import datetime

class Restaurant(TypedDict):
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
    date_added: datetime

class RestaurantListState(TypedDict):
    # User input
    user_message: str
    user_action: str  # "discover", "edit", "view"

    # Discovery process
    discovered_restaurants: List[Restaurant]
    search_results_raw: dict  # Raw search results from web

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
```

### 2.3 Configuration from `.env`

**Required Environment Variables:**
```
# Location Preferences (FR-1.1)
LOCATION_CITY=Washington DC

# Google Sheets
GOOGLE_SHEET_ID=<your-sheet-id>
GOOGLE_SHEET_NAME=Restaurant List
GOOGLE_CREDENTIALS_FILE=credentials.json

# LLM Configuration
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-5-mini

# [TODO: ADD ANY OTHER CONFIGURATION NEEDED]
```

---

## 3. Functional Requirements Implementation

### 3.1 Restaurant Discovery (FR-1.1)

**Authoritative Sources:**
- Eater DC
- Michelin Guide
- Washington Post Food section
- Washingtonian Magazine
- Infatuation

**Search Strategy:**
- Use Tavily AI for web search and browsing

**Implementation Method:**
- LLM uses Tavily to search through each source using filter criteria
- LLM flags each restaurant that meets the filter criteria
- LLM evaluates all discovered restaurants and ranks for each source
- LLM averages each source ranking to calculate an overall ranking

**Filter Criteria:**
- Location: Within `LOCATION_CITY`
- Only search web pages from authoritative sources 
- Only include restaurants mentioned in an article or web page on the source in the past year

### 3.2 Restaurant Evaluation (FR-1.2, FR-1.3)
- Create a separate ranking from 1.0-5.0 for each authoritative source. If the source does not have any information on the restaurant, do not set a ranking.
- Most importantly, PRIORITIZE restuarants on ranked or ordered lists from authoritative sources
- Secondly, PRIORITIZE restaurants based on the category of the list. For example, Washington Post and Michelin Guide have a star rating system
- Thirdly, prioritize based off qualitative descriptions in the sources. Judge the restaurant based on the following order: high quality of food, the innovation or "new"-ness of the cuisine, the quality of the cocktail list, the quality of the ambience, the quality of the service
- Create an overall ranking for each restaurant based on the average of the sources' ranking, ignoring sources that do not have a ranking.

### 3.3 Google Sheets Management (FR-2.1, FR-2.2)

**Sheet Schema:**
| Column | Type | Description |
|--------|------|-------------|
| Restaurant Name | Text | Official name |
| Booking Website | URL | OpenTable/Resy/Tock/restaurant site |
| Brief Description | Text | 1-3 sentence description of restaurant |
| Priority Reasons | Text | 1-3 sentences explaining the qualitative reasons that the restaurant is prioritized |
| Price Range | Text | $, $$, $$$, or $$$$ |
| Cuisine Type | Text | Italian, French, Japanese, etc. |
| Eater DC Rank | Float | 0.0 - 5.0 (0.0 if not ranked by source) |
| Michelin Guide Rank | Float | 0.0 - 5.0 (0.0 if not ranked by source) |
| Washington Post Rank | Float | 0.0 - 5.0 (0.0 if not ranked by source) |
| Washingtonian Rank | Float | 0.0 - 5.0 (0.0 if not ranked by source) |
| Infatuation Rank | Float | 0.0 - 5.0 (0.0 if not ranked by source) |
| Overall Priority Rank | Float | 0.0 - 5.0 (average of source rankings) |
| Date Added | Date | When added to list |

**Update Workflow:**
1. Fetch current list from Google Sheets
2. Compare discovered restaurants against current list
3. Identify Additions: New restaurants not in current list
4. Present recommendations to user in table showing:
   - Restaurant name
   - Brief description
   - Overall Priority Rank
   - Priority Reasons
5. Await user approval (graph interrupt)
6. Apply changes after confirmation

### 3.4 User Approval Workflow (FR-2.3)

**Recommendation Presentation Format:**

I found [X] new restaurants and [Y] potential removals:

NEW RESTAURANTS:
1. [Restaurant Name]
   Description: [Brief Description]
   Overall Priority Rank: [4.5/5.0]
   Priority Reasons: [Brief Explanation]

[... repeat for all additions ...]

**User Response Handling:**
- "Yes" / "Approve" / "Looks good" → Approve all
- "Add 1, 3, 5 but not 2, 4" → Partial approval
- "Tell me more about #2" → Request details
- "No" / "Cancel" → Cancel update

**Graph Interrupt:**
- Use LangGraph's `interrupt()` after `present_recommendations` node
- Resume graph after user provides input
- Store user approval in `user_approval` and `user_feedback` state fields

### 3.5 Conversational Editing (FR-2.2)

**Supported Commands:**
- "Remove [Restaurant Name] from my list"
- "Add [Restaurant Name] to my list" (manual addition)
- "Update [Restaurant Name] description to [new description]"
- "Change [Restaurant Name] priority to [Top/Great/etc]"
- **[TODO: USER - What other edit commands do you want to support?]**

**Implementation:**
- Route through `handle_conversational_edit` node
- Extract: action (add/remove/update), restaurant name, field, new value
- Apply change to Google Sheets after confirmation
- Use LLM to parse natural language intent

---

## 4. Node Implementations

### 4.1 Node: `search_sources`

**Purpose:** Search authoritative sources for new restaurants using Tavily AI

**Implementation Strategy:**
- Use Tavily AI's search and browse capabilities to query each authoritative source
- LLM examines search results and flags restaurants meeting filter criteria
- Extract restaurant details: name, booking website, description, cuisine type, price range

**Implementation Pseudocode:**
```python
def search_sources(state: RestaurantListState) -> RestaurantListState:
    """
    Search authoritative sources using Tavily AI.
    """
    from tavily import TavilyClient

    tavily_client = TavilyClient(api_key=config.get("TAVILY_API_KEY"))
    location = config.get("LOCATION_CITY")

    # Authoritative sources from Section 3.1
    sources = [
        "Eater DC",
        "Michelin Guide",
        "Washington Post Food",
        "Washingtonian Magazine",
        "Infatuation"
    ]

    all_discovered = []
    results_by_source = {}

    for source in sources:
        try:
            # Search for recent articles from this source
            search_query = f"{source} best new restaurants {location} 2024-2025"
            search_results = tavily_client.search(
                query=search_query,
                search_depth="advanced",
                max_results=10,
                include_domains=[get_source_domain(source)]
            )

            # Use LLM to parse search results and extract restaurants
            restaurants = llm_extract_restaurants(
                source=source,
                search_results=search_results,
                location=location
            )

            results_by_source[source] = restaurants
            all_discovered.extend(restaurants)

        except Exception as e:
            logger.error(f"Failed to search {source}: {e}")
            state["errors"].append(f"Source {source} failed: {str(e)}")

    # Deduplicate by restaurant name
    state["discovered_restaurants"] = deduplicate_restaurants(all_discovered)
    state["search_results_raw"] = results_by_source

    return state

def get_source_domain(source: str) -> str:
    """Map source names to their website domains."""
    domains = {
        "Eater DC": "dc.eater.com",
        "Michelin Guide": "guide.michelin.com",
        "Washington Post Food": "washingtonpost.com",
        "Washingtonian Magazine": "washingtonian.com",
        "Infatuation": "theinfatuation.com"
    }
    return domains.get(source, "")

def llm_extract_restaurants(source: str, search_results: dict, location: str) -> List[Restaurant]:
    """
    Use LLM to parse Tavily search results and extract restaurant details.

    Prompt the LLM to:
    - Identify restaurants mentioned in articles from the past year
    - Extract: name, description, cuisine type, price range, booking website
    - Only include upscale restaurants ($$-$$$$)
    - Exclude fast-casual, chains, budget options
    """
    # LLM call implementation here
    # Returns list of Restaurant objects
    pass
```

**Tools/Libraries:**
- `tavily-python`: Tavily AI client for web search
- OpenAI API: gpt-5-mini for parsing and extraction
- LangChain: For structured LLM outputs

**Error Handling:**
- Retry failed source searches once (max)
- Log failures but continue with other sources
- If all sources fail → set `errors` and route to `error_handler`

---

### 4.2 Node: `evaluate_restaurants`

**Purpose:** Rank restaurants per source and calculate overall priority rank (1.0-5.0)

**Implementation Strategy (from Section 3.2):**
1. For each authoritative source, create a separate ranking (1.0-5.0)
2. Prioritize restaurants on ranked/ordered lists from sources
3. Consider list category (e.g., Michelin stars, Washington Post ratings)
4. Evaluate qualitative descriptions based on: food quality, innovation, cocktails, ambience, service
5. Calculate overall rank as average of all source rankings

**Implementation Pseudocode:**
```python
def evaluate_restaurants(state: RestaurantListState) -> RestaurantListState:
    """
    Evaluate each restaurant by ranking it per source, then averaging.
    """
    evaluated_restaurants = []

    for restaurant in state["discovered_restaurants"]:
        # Get rankings from each source that mentioned this restaurant
        source_rankings = {}

        for source, restaurants_from_source in state["search_results_raw"].items():
            if restaurant["name"] in [r["name"] for r in restaurants_from_source]:
                # Use LLM to rank this restaurant for this specific source
                ranking = llm_rank_restaurant_for_source(
                    restaurant=restaurant,
                    source=source,
                    source_data=restaurants_from_source
                )
                if ranking:
                    source_rankings[source] = ranking

        # Calculate overall priority rank (average of source rankings)
        if source_rankings:
            overall_rank = sum(source_rankings.values()) / len(source_rankings)
            restaurant["priority_rank"] = round(overall_rank, 1)

            # Generate priority reasons
            restaurant["priority_reasons"] = llm_generate_priority_reasons(
                restaurant=restaurant,
                source_rankings=source_rankings
            )
        else:
            # No source rankings available
            restaurant["priority_rank"] = 0.0
            restaurant["priority_reasons"] = "No source rankings available"

        evaluated_restaurants.append(restaurant)

    # Filter out low priority restaurants (optional)
    state["discovered_restaurants"] = [
        r for r in evaluated_restaurants
        if r["priority_rank"] >= 2.0  # [TODO: USER - Filter out restaurants below 2.0? YES/NO]
    ]

    return state

def llm_rank_restaurant_for_source(
    restaurant: Restaurant,
    source: str,
    source_data: List[Restaurant]
) -> float:
    """
    Use LLM to rank a restaurant (1.0-5.0) based on a single source's data.

    Evaluation criteria (in priority order):
    1. Position on ranked/ordered lists
    2. Category of list (stars, awards, etc.)
    3. Qualitative descriptions:
       - High quality of food
       - Innovation/"new"-ness of cuisine
       - Quality of cocktail list
       - Quality of ambience
       - Quality of service

    Returns: float 1.0-5.0, or None if source has no info on this restaurant
    """
    # See Appendix A.1 for prompt template
    # LLM call implementation here
    pass

def llm_generate_priority_reasons(
    restaurant: Restaurant,
    source_rankings: dict
) -> str:
    """
    Generate 1-3 sentences explaining why this restaurant is prioritized.

    Example: "Ranked #3 on Eater DC's Essential 38. Featured in Washington Post's
    2024 best new restaurants with a focus on innovative French-Japanese fusion.
    Michelin Guide highlights exceptional cocktail program."
    """
    # LLM call implementation here
    pass
```

**LLM Integration:**
- Use OpenAI gpt-5-mini for all evaluation and ranking
- See Appendix A.1 for detailed prompt templates
- Use structured outputs (JSON mode) for reliable parsing

---

### 4.3 Node: `compare_lists`

**Purpose:** Identify additions by comparing discovered restaurants against current list

**Implementation Pseudocode:**
```python
def compare_lists(state: RestaurantListState) -> RestaurantListState:
    """
    Compare discovered restaurants against current list.
    Identify new restaurants to add.
    """
    current_names = {r["name"].lower() for r in state["current_list"]}
    discovered_names = {r["name"].lower() for r in state["discovered_restaurants"]}

    # Additions: in discovered but not in current
    state["restaurants_to_add"] = [
        r for r in state["discovered_restaurants"]
        if r["name"].lower() not in current_names
    ]

    # Removals: Not implemented in MVP
    # User can manually remove restaurants via conversational editing (Section 3.5)
    state["restaurants_to_remove"] = []

    return state
```

**Notes:**
- Case-insensitive name matching to avoid duplicates
- Removal detection not included in MVP - users can manually remove via chat
- Future enhancement: Detect closed restaurants by checking booking sites

---

### 4.4 Node: `present_recommendations`

**Purpose:** Format and present recommended additions to user

**Implementation Pseudocode:**
```python
def present_recommendations(state: RestaurantListState) -> RestaurantListState:
    """
    Format recommendations in user-friendly table format.
    """
    num_additions = len(state["restaurants_to_add"])

    if num_additions == 0:
        state["recommendation_message"] = "I didn't find any new restaurants to add. Your list is up to date!"
        return state

    # Build recommendation message
    message = f"I found {num_additions} new restaurant{'s' if num_additions > 1 else ''} for your list:\n\n"
    message += "NEW RESTAURANTS:\n"

    for i, restaurant in enumerate(state["restaurants_to_add"], 1):
        message += f"\n{i}. **{restaurant['name']}**\n"
        message += f"   Description: {restaurant['description']}\n"
        message += f"   Overall Priority Rank: {restaurant['priority_rank']}/5.0\n"
        message += f"   Priority Reasons: {restaurant['priority_reasons']}\n"
        message += f"   Cuisine: {restaurant['cuisine_type']} | Price: {restaurant['price_range']}\n"

    message += "\n\nWould you like to add these restaurants to your list?"

    state["recommendation_message"] = message
    return state
```

**Output Format (from Section 3.4):**
- Restaurant name
- Brief description
- Overall Priority Rank (X.X/5.0)
- Priority Reasons
- Additional metadata: cuisine type, price range

---

### 4.5 Node: `await_user_approval`

**Purpose:** Interrupt graph and wait for user confirmation (LangGraph interrupt point)

**Implementation Pseudocode:**
```python
def await_user_approval(state: RestaurantListState) -> RestaurantListState:
    """
    Interrupt the graph and wait for user input.
    This is handled by LangGraph's interrupt mechanism.
    """
    # This node doesn't modify state
    # LangGraph will pause execution here
    # User response will update state["user_approval"] and state["user_feedback"]
    return state
```

**Conditional Edge After Approval:**
```python
def route_after_approval(state: RestaurantListState) -> str:
    """
    Route to update_google_sheet if approved, otherwise END.
    """
    if state.get("user_approval") == True:
        return "update_google_sheet"
    else:
        return END
```

**Supported User Responses (from Section 3.4):**
- "Yes" / "Approve" / "Looks good" → Approve all
- "Add 1, 3, 5 but not 2, 4" → Partial approval (parse numbers)
- "Tell me more about #2" → Request additional details
- "No" / "Cancel" → Cancel update

---

### 4.6 Node: `update_google_sheet`

**Purpose:** Apply approved changes to Google Sheets

**Implementation Pseudocode:**
```python
def update_google_sheet(state: RestaurantListState) -> RestaurantListState:
    """
    Add approved restaurants to Google Sheet.
    """
    from src.clients.google_sheets_client import GoogleSheetsClient

    sheets_client = GoogleSheetsClient(
        spreadsheet_id=config.get("GOOGLE_SHEET_ID"),
        sheet_name=config.get("GOOGLE_SHEET_NAME"),
        credentials_file=config.get("GOOGLE_CREDENTIALS_FILE")
    )

    # Add new restaurants (schema from Section 3.3)
    for restaurant in state["restaurants_to_add"]:
        sheets_client.append_row([
            restaurant["name"],                    # Column A
            restaurant["booking_website"],         # Column B
            restaurant["description"],             # Column C
            restaurant["priority_reasons"],        # Column D
            restaurant["price_range"],             # Column E
            restaurant["cuisine_type"],            # Column F
            restaurant["eater_dc_rank"],           # Column G (float)
            restaurant["michelin_guide_rank"],     # Column H (float)
            restaurant["washington_post_rank"],    # Column I (float)
            restaurant["washingtonian_rank"],      # Column J (float)
            restaurant["infatuation_rank"],        # Column K (float)
            restaurant["priority_rank"],           # Column L (float)
            datetime.now().strftime("%Y-%m-%d")    # Column M
        ])

    # Update last discovery date
    state["last_discovery_date"] = datetime.now()

    logger.info(f"Added {len(state['restaurants_to_add'])} restaurants to Google Sheets")

    return state
```

**Google Sheets Schema (from Section 3.3):**
| Column | Field | Type |
|--------|-------|------|
| A | Restaurant Name | Text |
| B | Booking Website | URL |
| C | Brief Description | Text |
| D | Priority Reasons | Text |
| E | Price Range | Text |
| F | Cuisine Type | Text |
| G | Eater DC Rank | Float |
| H | Michelin Guide Rank | Float |
| I | Washington Post Rank | Float |
| J | Washingtonian Rank | Float |
| K | Infatuation Rank | Float |
| L | Overall Priority Rank | Float |
| M | Date Added | Date |

**Google Sheets Client:** See `src/clients/google_sheets_client.py`

---

### 4.7 Node: `handle_conversational_edit`

**Purpose:** Process ad-hoc user edits to the restaurant list

**Supported Commands (from Section 3.5):**
- "Remove [Restaurant Name] from my list"
- "Add [Restaurant Name] to my list" (manual addition)
- "Update [Restaurant Name] description to [new description]"
- "Change [Restaurant Name] priority to [X.X]"

**Implementation Pseudocode:**
```python
def handle_conversational_edit(state: RestaurantListState) -> RestaurantListState:
    """
    Parse natural language edit commands and prepare state for approval.
    """
    user_message = state["user_message"]

    # Use LLM to parse edit intent
    edit_intent = llm_parse_edit_command(user_message)

    # Examples of edit_intent structure:
    # {
    #   "action": "remove",
    #   "restaurant_name": "Restaurant X",
    #   "field": None,
    #   "new_value": None
    # }

    if edit_intent["action"] == "remove":
        # Find restaurant in current list
        restaurant = find_restaurant_by_name(
            state["current_list"],
            edit_intent["restaurant_name"]
        )
        if restaurant:
            state["restaurants_to_remove"] = [restaurant]
            state["recommendation_message"] = f"Remove {restaurant['name']} from your list?"
        else:
            state["recommendation_message"] = f"I couldn't find '{edit_intent['restaurant_name']}' in your list."

    elif edit_intent["action"] == "update":
        # Update specific field
        # Implementation for updating description, priority, etc.
        pass

    elif edit_intent["action"] == "add":
        # Manual addition (user provides details)
        # Implementation for adding a restaurant manually
        pass

    return state

def llm_parse_edit_command(user_message: str) -> dict:
    """
    Use LLM to parse natural language edit commands.
    Returns structured dict with action, restaurant_name, field, new_value.
    """
    # LLM call implementation
    pass
```

**Error Handling:**
- If restaurant name not found, inform user
- If command is ambiguous, ask for clarification
- All edits require user confirmation before applying

---

## 5. CLI Chat Interface

### 5.1 Overview

The RestaurantList Agent is designed to be used through a conversational CLI (Command Line Interface) chat experience. Users interact with the agent by typing natural language messages in the terminal, and the agent responds with formatted text output.

**Key Features:**
- Natural language conversation loop
- Real-time agent responses
- Interactive approval workflow (LangGraph interrupts)
- Formatted output (tables, lists, markdown)
- Graceful error handling and exit

### 5.2 Running the CLI Chat Interface

**Command:**
```bash
# Activate virtual environment
source .venv/bin/activate

# Run the RestaurantList agent in chat mode
python src/main.py --agent restaurant-list
```

**Startup Output:**
```
=================================================
   Date Night Reservation Agent
   RestaurantList Agent - v1.0
=================================================

I can help you discover new upscale DC restaurants and manage your restaurant list.

Try these commands:
  • "Find new restaurants"
  • "Update my restaurant list"
  • "Remove [Restaurant Name] from my list"
  • "Show me my current list"
  • Type 'exit' or 'quit' to end the session

=================================================

You: _
```

### 5.3 Chat Loop Architecture

**Flow:**
1. User enters message in terminal
2. Message is passed to LangGraph agent
3. Agent executes nodes until:
   - Completion (END node reached)
   - Interrupt point (user approval needed)
4. Agent response is formatted and displayed
5. If interrupted, wait for user input and resume
6. Loop continues until user exits

**Implementation Location:** `src/main.py`

### 5.4 LangGraph Interrupt Handling in CLI

**Challenge:** LangGraph's `interrupt()` pauses graph execution and requires external input to resume.

**CLI Implementation Strategy:**

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

# Initialize graph with checkpointer for interrupt support
memory = MemorySaver()
graph = StateGraph(RestaurantListState)
# ... add nodes and edges ...
compiled_graph = graph.compile(checkpointer=memory, interrupt_before=["await_user_approval"])

# Chat loop
thread_id = {"configurable": {"thread_id": "restaurant-list-session"}}
state = {"user_message": "", "user_action": "discover"}

while True:
    user_input = input("You: ").strip()

    if user_input.lower() in ["exit", "quit"]:
        break

    # Update state with user message
    state["user_message"] = user_input

    # Invoke graph
    result = compiled_graph.invoke(state, config=thread_id)

    # Check if graph was interrupted
    if "recommendation_message" in result and result["recommendation_message"]:
        # Display agent's recommendation
        print(f"\nAgent: {result['recommendation_message']}\n")

        # If graph is waiting for approval, get user response
        if compiled_graph.get_state(thread_id).next == ("await_user_approval",):
            approval_input = input("You: ").strip()

            # Parse approval response
            approval, feedback = parse_user_approval(approval_input)
            result["user_approval"] = approval
            result["user_feedback"] = feedback

            # Resume graph with approval
            state = result
            final_result = compiled_graph.invoke(state, config=thread_id)

            # Display completion message
            if final_result.get("user_approval"):
                print(f"\nAgent: Successfully updated your restaurant list!\n")
            else:
                print(f"\nAgent: Update cancelled.\n")

    # Update state for next iteration
    state = result
```

**Key Components:**
- **MemorySaver checkpointer**: Enables graph interrupts and resume
- **interrupt_before**: Specifies nodes to pause at (e.g., `await_user_approval`)
- **thread_id**: Maintains conversation context across interrupts
- **get_state().next**: Check if graph is waiting at interrupt point

### 5.5 Example CLI Sessions

#### 5.5.1 Full Discovery Flow

```
You: Find new restaurants for my list

Agent: Starting restaurant discovery across 6 authoritative sources...
[Discovery process runs for ~2-3 minutes]

Agent: I found 8 new restaurants for your list:

NEW RESTAURANTS:

1. **Moon Rabbit**
   Description: Vietnamese fine dining in The Wharf featuring elevated takes
   on regional Vietnamese cuisine in an elegant setting.
   Overall Priority Rank: 4.5/5.0
   Priority Reasons: Ranked #5 on Eater DC's Essential 38. Featured in
   Washington Post's 2024 best new restaurants for innovative Vietnamese
   cuisine. Michelin Guide highlights exceptional cocktail program.
   Cuisine: Vietnamese | Price: $$$

2. **Jônt**
   Description: Modern American tasting menu restaurant showcasing seasonal
   Mid-Atlantic ingredients with creative presentations.
   Overall Priority Rank: 4.8/5.0
   Priority Reasons: Michelin one-star restaurant. Ranked #2 on Washingtonian's
   100 Best Restaurants. Eater DC calls it "DC's most exciting tasting menu."
   Cuisine: Modern American | Price: $$$$

[... 6 more restaurants ...]

Would you like to add these restaurants to your list?

You: Yes, add all of them

Agent: Successfully updated your restaurant list! Added 8 new restaurants to
your Google Sheet.

You: _
```

#### 5.5.2 Partial Approval

```
You: Update my restaurant list

Agent: I found 5 new restaurants for your list:

NEW RESTAURANTS:

1. **Causa**
   [... details ...]

2. **Reverie**
   [... details ...]

3. **Albi**
   [... details ...]

4. **Oyster Oyster**
   [... details ...]

5. **Cranes**
   [... details ...]

Would you like to add these restaurants to your list?

You: Add 1, 2, and 4, but skip 3 and 5

Agent: Got it! I'll add:
  • Causa
  • Reverie
  • Oyster Oyster

And skip:
  • Albi
  • Cranes

Is that correct?

You: Yes

Agent: Successfully updated your restaurant list! Added 3 new restaurants.

You: _
```

#### 5.5.3 Conversational Editing

```
You: Remove Little Pearl from my list

Agent: I found "Little Pearl" in your restaurant list. Are you sure you want
to remove it?

Restaurant: Little Pearl
Description: Neighborhood restaurant serving Mediterranean-inspired cuisine...
Priority Rank: 4.2/5.0

You: Yes, remove it

Agent: Successfully removed "Little Pearl" from your restaurant list.

You: _
```

#### 5.5.4 Requesting More Information

```
You: Find new restaurants

Agent: I found 3 new restaurants for your list:

1. **Maydan**
   Description: Middle Eastern restaurant featuring wood-fired cooking...
   Overall Priority Rank: 4.7/5.0
   [...]

2. **Tail Up Goat**
   Description: Mediterranean-inspired neighborhood spot...
   Overall Priority Rank: 4.3/5.0
   [...]

3. **Sababa**
   Description: Israeli restaurant with creative small plates...
   Overall Priority Rank: 3.8/5.0
   [...]

Would you like to add these restaurants to your list?

You: Tell me more about #2

Agent: **Tail Up Goat** - Additional Details:

Located in Adams Morgan, Tail Up Goat is known for:
  • Signature dish: Bread with whipped feta and honey
  • Mediterranean and Greek-inspired menu with creative twists
  • Cozy, intimate atmosphere perfect for date nights
  • Strong wine list focused on natural wines
  • Chef-owned restaurant with seasonal menu changes

Source Rankings:
  • Eater DC Essential 38: Ranked #12
  • Washingtonian: 4.5/5.0 rating
  • Michelin Guide: Mentioned favorably for neighborhood charm

Booking: Available on Resy
Website: tailupgoat.com

Would you still like to add all 3 restaurants, or would you like to make
specific selections?

You: Add all 3

Agent: Successfully updated your restaurant list! Added 3 new restaurants.

You: _
```

#### 5.5.5 Error Handling

```
You: Find new restaurants

Agent: Starting restaurant discovery...

[Error occurs during Tavily API call]

Agent: I encountered an error during restaurant discovery.

**What happened:** The discovery process failed while searching restaurant sources.

**Technical Details:**
  • Tavily API connection timeout (source: Eater DC)
  • Failed after 2 retry attempts

Would you like me to try again or cancel this discovery?

You: Try again

Agent: Starting restaurant discovery (retry 1/1)...

[Discovery succeeds]

Agent: I found 6 new restaurants for your list:
[... continues normally ...]

You: _
```

### 5.6 Message Formatting Guidelines

**Agent Response Format:**
- Use markdown formatting for readability in terminal
- Bold restaurant names: `**Restaurant Name**`
- Bullet lists for options: `  • Option 1`
- Clear section headers: `NEW RESTAURANTS:`, `Would you like to...?`
- Blank lines between restaurant entries for readability
- Show progress indicators for long-running operations

**User Input Parsing:**
- Case-insensitive command matching
- Natural language flexibility: "yes", "Yes", "yeah", "looks good" all work
- Number parsing: "Add 1, 3, 5" or "Add restaurants 1 and 3"
- Restaurant name matching: exact match with fallback to fuzzy matching

### 5.7 Implementation Pseudocode

**File:** `src/main.py`

```python
import sys
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agents.restaurant_list_agent import (
    RestaurantListState,
    build_restaurant_list_graph
)
from src.utils.logger import get_logger
from src.utils.config import config

logger = get_logger(__name__)

def parse_user_approval(user_input: str) -> tuple[bool, str]:
    """
    Parse user approval input into (approval: bool, feedback: str).

    Examples:
    - "yes" → (True, "")
    - "no" → (False, "")
    - "Add 1, 3, 5" → (True, "partial: [1, 3, 5]")
    - "Tell me more about #2" → (False, "more_info: 2")
    """
    user_input_lower = user_input.lower().strip()

    # Full approval
    if user_input_lower in ["yes", "y", "approve", "looks good", "add all", "add them"]:
        return (True, "")

    # Rejection
    if user_input_lower in ["no", "n", "cancel", "skip", "don't add"]:
        return (False, "cancelled")

    # Partial approval: "Add 1, 3, 5" or "Add restaurants 1 and 3"
    if "add" in user_input_lower:
        # Use LLM or regex to extract numbers
        numbers = extract_numbers_from_text(user_input)
        if numbers:
            return (True, f"partial: {numbers}")

    # Request for more info: "Tell me more about #2"
    if "more" in user_input_lower or "tell me" in user_input_lower:
        numbers = extract_numbers_from_text(user_input)
        if numbers:
            return (False, f"more_info: {numbers[0]}")

    # Default: treat as rejection and ask for clarification
    return (False, "unclear")

def extract_numbers_from_text(text: str) -> list[int]:
    """Extract numbers from text like 'Add 1, 3, 5' → [1, 3, 5]"""
    import re
    return [int(n) for n in re.findall(r'\d+', text)]

def format_startup_message() -> str:
    """Display welcome message when CLI starts."""
    return """
=================================================
   Date Night Reservation Agent
   RestaurantList Agent - v1.0
=================================================

I can help you discover new upscale DC restaurants and manage your restaurant list.

Try these commands:
  • "Find new restaurants"
  • "Update my restaurant list"
  • "Remove [Restaurant Name] from my list"
  • "Show me my current list"
  • Type 'exit' or 'quit' to end the session

=================================================
"""

def run_restaurant_list_cli():
    """
    Main CLI chat loop for RestaurantList agent.
    """
    print(format_startup_message())

    # Build LangGraph
    graph = build_restaurant_list_graph()
    memory = MemorySaver()
    compiled_graph = graph.compile(
        checkpointer=memory,
        interrupt_before=["await_user_approval"]
    )

    # Session configuration
    thread_id = {"configurable": {"thread_id": f"restaurant-list-{datetime.now().isoformat()}"}}
    state = {
        "user_message": "",
        "user_action": "",
        "discovered_restaurants": [],
        "current_list": [],
        "restaurants_to_add": [],
        "restaurants_to_remove": [],
        "recommendation_message": "",
        "user_approval": None,
        "user_feedback": None,
        "errors": [],
        "retry_count": 0,
        "last_discovery_date": None,
        "search_results_raw": {}
    }

    logger.info("RestaurantList CLI started", extra={"thread_id": thread_id})

    try:
        while True:
            # Get user input
            user_input = input("\nYou: ").strip()

            # Handle exit
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\nAgent: Goodbye! Happy dining!\n")
                logger.info("User ended CLI session")
                break

            # Skip empty input
            if not user_input:
                continue

            logger.info(f"User input: {user_input}")

            # Update state
            state["user_message"] = user_input
            state["user_approval"] = None
            state["user_feedback"] = None

            # Invoke graph
            try:
                print("\nAgent: ", end="", flush=True)
                result = compiled_graph.invoke(state, config=thread_id)

                # Display agent response
                if result.get("recommendation_message"):
                    print(result["recommendation_message"])

                # Check if graph is interrupted (waiting for approval)
                graph_state = compiled_graph.get_state(thread_id)
                if graph_state.next == ("await_user_approval",):
                    # Wait for user approval
                    approval_input = input("\nYou: ").strip()
                    logger.info(f"User approval input: {approval_input}")

                    # Parse approval
                    approval, feedback = parse_user_approval(approval_input)

                    # Handle unclear responses
                    if feedback == "unclear":
                        print("\nAgent: I didn't understand that. Please respond with:")
                        print("  • 'Yes' or 'Approve' to add all")
                        print("  • 'Add 1, 3, 5' to add specific restaurants")
                        print("  • 'No' or 'Cancel' to skip")
                        continue

                    # Handle "more info" requests
                    if feedback.startswith("more_info:"):
                        restaurant_num = int(feedback.split(":")[1])
                        # Display more info (implementation in separate function)
                        print(f"\n{display_restaurant_details(result['restaurants_to_add'][restaurant_num - 1])}")
                        continue

                    # Update state with approval
                    result["user_approval"] = approval
                    result["user_feedback"] = feedback

                    # Resume graph
                    final_result = compiled_graph.invoke(result, config=thread_id)

                    # Display completion message
                    if final_result.get("user_approval"):
                        num_added = len(final_result.get("restaurants_to_add", []))
                        print(f"\nAgent: Successfully updated your restaurant list! Added {num_added} restaurant{'s' if num_added != 1 else ''}.\n")
                        logger.info(f"Added {num_added} restaurants to list")
                    else:
                        print("\nAgent: Update cancelled.\n")
                        logger.info("User cancelled update")

                    state = final_result
                else:
                    # Graph completed without interrupt
                    state = result

            except Exception as e:
                logger.error(f"Error during graph execution: {e}", exc_info=True)
                print(f"\nAgent: I encountered an unexpected error: {str(e)}\n")
                print("Please try again or type 'exit' to quit.\n")

    except KeyboardInterrupt:
        print("\n\nAgent: Session interrupted. Goodbye!\n")
        logger.info("User interrupted session with Ctrl+C")

    except Exception as e:
        logger.error(f"Fatal error in CLI loop: {e}", exc_info=True)
        print(f"\nFatal error: {str(e)}\n")
        sys.exit(1)

def display_restaurant_details(restaurant: dict) -> str:
    """Format detailed restaurant information for CLI display."""
    return f"""**{restaurant['name']}** - Additional Details:

Description: {restaurant['description']}

Priority Rank: {restaurant['priority_rank']}/5.0
Priority Reasons: {restaurant['priority_reasons']}

Cuisine: {restaurant['cuisine_type']}
Price Range: {restaurant['price_range']}
Booking: {restaurant['booking_website']}
"""

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Date Night Reservation Agent")
    parser.add_argument(
        "--agent",
        choices=["restaurant-list", "reservation-booking"],
        default="restaurant-list",
        help="Which agent to run"
    )

    args = parser.parse_args()

    if args.agent == "restaurant-list":
        run_restaurant_list_cli()
    else:
        print(f"Agent '{args.agent}' not yet implemented.")
```

### 5.8 CLI-Specific Requirements

**Terminal Compatibility:**
- Support standard terminals (bash, zsh, Terminal.app, iTerm2)
- Handle Ctrl+C gracefully (KeyboardInterrupt)
- Use UTF-8 encoding for special characters (bullets, em-dashes)

**User Experience:**
- Response time feedback: Show "Agent: " immediately, then stream response
- For long operations (discovery), show progress: "Searching Eater DC... (1/6)"
- Clear visual separation between user and agent messages
- Consistent prompt: Always show "You: " for user input

**Session Management:**
- Each CLI session gets unique thread_id for LangGraph checkpointer
- State persists within session for context
- Logs all user inputs and agent responses for debugging

### 5.9 Testing the CLI

**Manual Testing Checklist:**
- [ ] CLI starts successfully with welcome message
- [ ] User can enter messages and receive responses
- [ ] Discovery flow works end-to-end with approval
- [ ] Partial approval parsing works correctly
- [ ] "Tell me more" requests display details
- [ ] Conversational editing works (remove, add, update)
- [ ] Error messages display clearly
- [ ] Ctrl+C exits gracefully
- [ ] "exit" and "quit" commands work
- [ ] LangGraph interrupts and resumes correctly
- [ ] All user responses are logged to JSON logs

**Automated Testing:**
- Mock user input with predefined sequences
- Verify graph execution and state transitions
- Test approval parsing edge cases
- Validate output formatting

---

## 6. Error Handling & Retry Logic

### 6.1 Retry Strategy (from PRD NFR-5.2)

**Retry Rules:**
- Any node failure → retry once
- After second failure → route to `error_handler` node
- `error_handler` presents both natural language and technical error to user

**Implementation:**
```python
def error_handler(state: RestaurantListState) -> RestaurantListState:
    """
    Handle errors and present to user with retry option.
    """
    errors_list = "\n".join(state["errors"])

    error_message = f"""I encountered an error during restaurant discovery.

**What happened:** The discovery process failed while searching restaurant sources.

**Technical Details:**
{errors_list}

Would you like me to try again or cancel this discovery?"""

    state["recommendation_message"] = error_message
    return state
```

**Retry Mechanism:**
- Track retry count in `state["retry_count"]`
- Max retries: 1 (total of 2 attempts)
- After max retries exceeded, inform user and END

---

### 6.2 Timeout Handling

**Node Timeouts (from PRD NFR-5.1):**
- `search_sources`: 5 minutes max (searches multiple sources)
- `evaluate_restaurants`: 3 minutes max (multiple LLM calls)
- `update_google_sheet`: 1 minute max
- Other nodes: 1 minute max

**Implementation:**
```python
# Configure timeouts in LangGraph
from langgraph.graph import StateGraph

graph = StateGraph(RestaurantListState)
graph.add_node("search_sources", search_sources, timeout=300)  # 5 min
graph.add_node("evaluate_restaurants", evaluate_restaurants, timeout=180)  # 3 min
graph.add_node("update_google_sheet", update_google_sheet, timeout=60)  # 1 min
# ... etc
```

**Timeout Behavior:**
- If timeout occurs, treat as node failure
- Follow retry strategy (Section 6.1)
- Log timeout event with node name and duration

---

## 7. Testing Strategy

### 7.1 Unit Tests

**Test Coverage:**
- [ ] `llm_extract_restaurants()` with mock Tavily search results
- [ ] `llm_rank_restaurant_for_source()` with various source data formats
- [ ] `llm_generate_priority_reasons()` output validation
- [ ] `compare_lists()` with overlapping/non-overlapping lists
- [ ] `deduplicate_restaurants()` with case variations
- [ ] Google Sheets CRUD operations (mocked)
- [ ] `llm_parse_edit_command()` with various edit patterns

**Testing LLM Calls:**
- Mock OpenAI API responses using `pytest-mock`
- Test structured output parsing (JSON mode)
- Validate error handling for malformed LLM responses

---

### 7.2 Integration Tests

**Test Scenarios:**
1. **Full discovery flow** with mocked Tavily responses
   - Mock 6 authoritative sources
   - Verify deduplication across sources
   - Validate ranking calculations
2. **User approval → Google Sheets update** (end-to-end)
   - Test with test Google Sheet
   - Verify correct schema mapping
3. **Conversational edit:** "Remove Restaurant X"
   - Test intent parsing
   - Verify Google Sheets deletion
4. **Error handling:** Tavily API failure
   - Mock API timeout
   - Verify retry logic
5. **Error handling:** Google Sheets API failure
   - Mock authentication failure
   - Verify error message presentation

---

### 7.3 Manual Testing Checklist

**Pre-Implementation Testing:**
- [ ] Test Tavily API with real DC restaurant queries
- [ ] Verify LLM can parse real Eater DC, Michelin Guide pages
- [ ] Test Google Sheets API connection with credentials

**Post-Implementation Testing:**
- [ ] Run discovery on real DC restaurant sources
- [ ] Verify ranking accuracy against manual evaluation
- [ ] Test user approval interrupt and resume in LangGraph
- [ ] Verify Google Sheets updates with correct schema
- [ ] Test partial approval ("Add 1, 3, not 2")
- [ ] Test conversational edits for all supported commands
- [ ] Verify JSON logging for all operations
- [ ] Test timeout behavior (artificially delay nodes)

---

## 8. Deployment & Operations

### 8.1 Logging

**Log Events (JSON format via `src/utils/logger.py`):**
- Discovery process started/completed
- Each source search:
  - Source name
  - Number of restaurants found
  - Duration
  - Success/failure
- Tavily API calls (request/response)
- LLM evaluation calls:
  - Restaurant name
  - Source
  - Ranking assigned
- Restaurant deduplication results
- User approval decisions (approved/rejected/partial)
- Google Sheets updates:
  - Number of rows added
  - Restaurant names
- All errors with stack traces and context

**Log Format:** JSON (using `src/utils/logger.py`)

**Example:**
```json
{
  "timestamp": "2025-12-31T10:30:00Z",
  "level": "INFO",
  "agent": "RestaurantListAgent",
  "node": "search_sources",
  "event": "source_search_completed",
  "data": {
    "source": "Eater DC",
    "restaurants_found": 12,
    "duration_seconds": 3.2
  }
}
```

```json
{
  "timestamp": "2025-12-31T10:32:15Z",
  "level": "INFO",
  "agent": "RestaurantListAgent",
  "node": "evaluate_restaurants",
  "event": "restaurant_ranked",
  "data": {
    "restaurant_name": "Little Pearl",
    "source": "Eater DC",
    "source_rank": 4.5,
    "overall_rank": 4.3
  }
}
```

---

### 8.2 Performance Monitoring

**Metrics to Track:**
- Discovery process duration (target: < 5 minutes from PRD NFR-5.1)
- Tavily API response times
- OpenAI API response times (LLM calls)
- Google Sheets API response times
- User approval time (time between present_recommendations and user response)
- Number of restaurants discovered per source
- Number of restaurants added to list per discovery run

**Performance Targets (from PRD):**
- Total discovery time: < 5 minutes
- Per-source search: < 60 seconds
- LLM evaluation per restaurant: < 10 seconds

---

### 8.3 Data Backup

**Google Sheets Backup Strategy:**

**Recommended Approach:** Option A - No backup (Google Sheets has built-in version history)

**Rationale:**
- Google Sheets maintains version history automatically
- Users can revert changes via Google Sheets UI
- Reduces complexity and local storage requirements
- For critical backups, user can manually export sheet

**Alternative (if needed):**
```python
def backup_google_sheet_to_json(state: RestaurantListState):
    """
    Export current Google Sheet to local JSON before updates.
    """
    backup_path = f"data/backups/restaurant_list_{datetime.now().isoformat()}.json"
    with open(backup_path, 'w') as f:
        json.dump(state["current_list"], f, indent=2)
    logger.info(f"Backed up restaurant list to {backup_path}")
```

---

## 9. Future Enhancements (Post-MVP)

**Potential Additions:**
- [ ] **Automatic discovery scheduling:** Weekly discovery runs via cron job
- [ ] **Visit tracking:** Mark restaurants as "visited" after reservation booking, track date and notes
- [ ] **Cuisine preferences:** Filter or boost rankings based on cuisine type preferences
- [ ] **Social media integration:** Scrape Instagram/TikTok for trending DC restaurants
- [ ] **Natural language search:** "Find me a romantic Italian spot under $100" within existing list
- [ ] **Reservation integration:** Link to reservation booking agent, show which restaurants have availability
- [ ] **Collaborative filtering:** If multiple users, suggest restaurants based on similar preferences
- [ ] **Seasonal updates:** Automatically re-rank restaurants based on seasonal menus or recent reviews
- [ ] **Neighborhood filters:** Organize restaurants by DC neighborhood
- [ ] **Price alerts:** Notify when restaurants add special menus or prix fixe options

---

## 10. Open Questions & Decisions Needed

**For User to Decide:**

1. **Low Priority Filter (Section 4.2):** Exclude restaurants ranked below 2.0?
   - [ ] **Recommendation:** YES - Filter out restaurants below 2.0 to keep list focused on top-tier options
   - [ ] Decision: _________________

2. **Partial Approval Parsing (Section 4.5):** How to handle "Add 1, 3, 5 but not 2, 4"?
   - [ ] **Recommendation:** Use LLM to parse numbers and apply selective additions
   - [ ] Decision: _________________

3. **Manual Restaurant Addition (Section 4.7):** What details should user provide?
   - [ ] **Recommendation:** Require: name, booking website. Optional: description, cuisine, price range
   - [ ] Decision: _________________

4. **Removal Detection (Future):** How to identify closed restaurants?
   - [ ] **Options:**
     - Check booking site availability via API
     - Manual removal only via conversational editing
     - Google Places API status check
   - [ ] Decision: _________________

5. **Duplicate Restaurant Matching:** How strict should name matching be?
   - [ ] **Current:** Case-insensitive exact match
   - [ ] **Alternative:** Fuzzy matching (e.g., "Le Diplomate" vs "Le Diplomaté")
   - [ ] Decision: _________________

6. **Booking Website Field (Section 3.3):** What if restaurant has no online booking?
   - [ ] **Options:**
     - Store restaurant website
     - Store phone number
     - Mark as "Call to book"
   - [ ] Decision: _________________

7. **Conversational Edit Confirmation (Section 4.7):** Require confirmation for all edits?
   - [ ] **Recommendation:** YES - Always confirm before modifying Google Sheets
   - [ ] Decision: _________________

---

## 11. Implementation Checklist

**Phase 1: Core Discovery & Extraction**
- [ ] Set up Tavily API client and test credentials
- [ ] Implement `search_sources` node with Tavily integration
- [ ] Implement `llm_extract_restaurants()` with structured outputs
- [ ] Test extraction on real Eater DC, Michelin Guide pages
- [ ] Create unit tests for restaurant extraction

**Phase 2: Restaurant Evaluation**
- [ ] Implement `llm_rank_restaurant_for_source()` prompt and parsing
- [ ] Implement `llm_generate_priority_reasons()` prompt
- [ ] Implement `evaluate_restaurants` node with ranking logic
- [ ] Create unit tests for ranking calculations
- [ ] Validate rankings against manual evaluation

**Phase 3: List Management**
- [ ] Implement `fetch_current_list` from Google Sheets
- [ ] Implement `compare_lists` with deduplication
- [ ] Implement `present_recommendations` formatting
- [ ] Create mock tests for comparison logic
- [ ] Test with real Google Sheets

**Phase 4: User Interaction**
- [ ] Implement `await_user_approval` LangGraph interrupt
- [ ] Implement approval parsing (full, partial, cancel)
- [ ] Implement `update_google_sheet` node with correct schema
- [ ] Test end-to-end flow: discovery → approval → update

**Phase 5: Conversational Editing**
- [ ] Implement `llm_parse_edit_command()` for natural language parsing
- [ ] Implement `handle_conversational_edit` node
- [ ] Support "remove", "add", "update" commands
- [ ] Test various edit patterns and edge cases

**Phase 6: Error Handling & Retry**
- [ ] Implement retry logic for all nodes
- [ ] Implement `error_handler` node with clear error messages
- [ ] Add timeout handling for long-running nodes
- [ ] Add comprehensive JSON logging
- [ ] Test failure scenarios (API timeout, auth failure, etc.)

**Phase 7: Graph Integration**
- [ ] Wire all nodes into LangGraph StateGraph
- [ ] Configure edges and conditional routing
- [ ] Set up node timeouts
- [ ] Configure interrupt points
- [ ] Test graph execution end-to-end

**Phase 8: CLI Chat Interface**
- [ ] Implement `run_restaurant_list_cli()` in `src/main.py`
- [ ] Implement `parse_user_approval()` for parsing user responses
- [ ] Implement LangGraph interrupt/resume handling in CLI
- [ ] Add message formatting and display functions
- [ ] Add Ctrl+C graceful exit handling
- [ ] Test CLI conversation flow end-to-end
- [ ] Validate all user input patterns (approval, partial, more info)

**Phase 9: Final Testing & Deployment**
- [ ] Run full discovery on real DC sources
- [ ] Verify Google Sheets updates with correct data
- [ ] Test all conversational patterns in CLI
- [ ] Test all CLI interaction scenarios (Section 5.5)
- [ ] Validate JSON logging output
- [ ] Performance testing (measure discovery time)
- [ ] Integrate with frontend chat interface (future)

---

## Appendix A: Example Prompts

### A.1 LLM Restaurant Extraction Prompt

**Purpose:** Extract restaurant details from Tavily search results

**System Prompt:**
```
You are a restaurant data extraction assistant. Your job is to parse web search results and extract structured information about upscale restaurants in Washington DC.
```

**User Prompt Template:**
```
I searched {source_name} and found the following web pages. Extract all restaurants mentioned that meet these criteria:

FILTER CRITERIA:
- Location: Washington DC area
- Price range: $$, $$$, or $$$$
- Upscale/fine dining (not fast-casual or chains)
- Mentioned in an article or list from the past year

SEARCH RESULTS:
{tavily_search_results}

For each restaurant that meets the criteria, extract:
1. Restaurant name (official name)
2. Brief description (1-3 sentences from the article)
3. Cuisine type (e.g., Italian, French, Japanese)
4. Price range ($, $$, $$$, $$$$)
5. Booking website URL (if mentioned, otherwise empty)

Respond in JSON format:
{
  "restaurants": [
    {
      "name": "Restaurant Name",
      "description": "Brief description...",
      "cuisine_type": "Italian",
      "price_range": "$$$",
      "booking_website": "https://..."
    }
  ]
}
```

---

### A.2 LLM Ranking Prompt

**Purpose:** Rank a restaurant (1.0-5.0) based on a single source's data

**System Prompt:**
```
You are a restaurant ranking expert. Your job is to evaluate and rank restaurants based on authoritative DC food sources.
```

**User Prompt Template:**
```
Evaluate this restaurant based on information from {source_name}:

RESTAURANT:
Name: {restaurant_name}
Description: {description}
Cuisine: {cuisine_type}
Price Range: {price_range}

SOURCE DATA FROM {source_name}:
{source_specific_context}

RANKING CRITERIA (in priority order):
1. Position on ranked/ordered lists (e.g., "Top 10", "#3 on Essential 38")
2. Category of list (e.g., Michelin stars, "Best New Restaurants")
3. Qualitative descriptions:
   - High quality of food
   - Innovation or "new"-ness of cuisine
   - Quality of cocktail list
   - Quality of ambience
   - Quality of service

Assign a ranking from 1.0 to 5.0:
- 5.0: Exceptional (Top tier, starred, #1-3 on major lists)
- 4.0: Excellent (Featured prominently, highly recommended)
- 3.0: Very Good (Mentioned favorably, solid choice)
- 2.0: Good (Mentioned, but not standout)
- 1.0: Mentioned only (minimal info or endorsement)

Respond in JSON format:
{
  "ranking": 4.5,
  "reasoning": "Ranked #3 on Eater DC's Essential 38. Highlighted for innovative French-Japanese fusion and exceptional cocktail program."
}
```

---

### A.3 LLM Priority Reasons Prompt

**Purpose:** Generate 1-3 sentences explaining restaurant priority

**System Prompt:**
```
You are a concise restaurant recommendation writer. Generate brief, compelling reasons for why a restaurant is prioritized.
```

**User Prompt Template:**
```
Generate a brief explanation (1-3 sentences) for why this restaurant is prioritized for an upscale date night list:

RESTAURANT:
Name: {restaurant_name}
Overall Ranking: {overall_rank}/5.0

SOURCE RANKINGS:
{source_rankings_dict}

Focus on:
- Notable list placements or awards
- Standout features (food quality, innovation, ambience, cocktails)
- Recent recognition or acclaim

Keep it concise and compelling.

Respond in plain text (no JSON).
```

**Example Output:**
```
Ranked #3 on Eater DC's Essential 38 with a 4.5 rating. Featured in Washington Post's 2024 best new restaurants for innovative French-Japanese fusion cuisine. Michelin Guide highlights exceptional cocktail program and romantic ambience.
```

---

### A.4 LLM Edit Command Parsing Prompt

**Purpose:** Parse natural language edit commands

**System Prompt:**
```
You are a command parser for restaurant list management. Parse user requests into structured actions.
```

**User Prompt Template:**
```
Parse this user command into a structured action:

USER COMMAND: "{user_message}"

Possible actions:
- "remove": User wants to remove a restaurant
- "add": User wants to manually add a restaurant
- "update": User wants to update restaurant details

Extract:
1. Action type
2. Restaurant name (if mentioned)
3. Field to update (if applicable): description, priority_rank, etc.
4. New value (if applicable)

Respond in JSON format:
{
  "action": "remove",
  "restaurant_name": "Restaurant X",
  "field": null,
  "new_value": null
}
```

**Example Inputs/Outputs:**

Input: "Remove Little Pearl from my list"
```json
{
  "action": "remove",
  "restaurant_name": "Little Pearl",
  "field": null,
  "new_value": null
}
```

Input: "Update the description for Maydan to emphasize their wood-fired cooking"
```json
{
  "action": "update",
  "restaurant_name": "Maydan",
  "field": "description",
  "new_value": "Emphasize wood-fired cooking"
}
```

---

### A.5 Recommendation Presentation Template

**Format for presenting discoveries to user (Section 3.4):**

```
I found {num_additions} new restaurant{s} for your list:

NEW RESTAURANTS:

1. **Restaurant Name**
   Description: Brief 1-3 sentence description from sources
   Overall Priority Rank: 4.5/5.0
   Priority Reasons: Explanation based on source rankings
   Cuisine: Italian | Price: $$$

2. **Another Restaurant**
   ...

Would you like to add these restaurants to your list?

Reply with:
- "Yes" or "Approve all" to add everything
- "Add restaurants 1, 3, 5" for partial approval
- "Tell me more about #2" for additional details
- "No" or "Cancel" to skip this update
```

---

**END OF SPECIFICATION**

*This document should be reviewed and all open questions in Section 9 resolved before beginning LangGraph implementation.*
