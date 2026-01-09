"""
Main entry point for the Date Night Reservation Agent.

Provides CLI chat interface for RestaurantList Agent.
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config
from utils.logger import setup_logger
from utils.cache import clear_cache, get_cache_stats
from clients.google_sheets_client import GoogleSheetsClient
from agents.restaurant_list_agent import build_restaurant_list_graph, RestaurantListState

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

logger = setup_logger(__name__)


# ============================================================================
# CLI Helper Functions
# ============================================================================

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
    if user_input_lower in ["yes", "y", "approve", "looks good", "add all", "add them", "ok"]:
        return (True, "")

    # Rejection
    if user_input_lower in ["no", "n", "cancel", "skip", "don't add", "nope"]:
        return (False, "cancelled")

    # Partial approval: "Add 1, 3, 5" or "Add restaurants 1 and 3"
    if "add" in user_input_lower:
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


# ============================================================================
# CLI Chat Interface
# ============================================================================

def run_restaurant_list_cli():
    """
    Main CLI chat loop for RestaurantList agent.
    """
    print(format_startup_message())

    # Build LangGraph WITHOUT interrupts - we'll handle approval manually
    graph = build_restaurant_list_graph()
    memory = MemorySaver()
    compiled_graph = graph.compile(checkpointer=memory)

    # Session configuration
    thread_id = {"configurable": {"thread_id": f"restaurant-list-{datetime.now().isoformat()}"}}
    state: RestaurantListState = {
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

                # Check if we need user approval (recommendations were presented)
                if result.get("restaurants_to_add") and len(result.get("restaurants_to_add", [])) > 0:
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
                        if restaurant_num <= len(result['restaurants_to_add']):
                            print(f"\n{display_restaurant_details(result['restaurants_to_add'][restaurant_num - 1])}")
                        continue

                    # Handle partial approval
                    if feedback.startswith("partial:"):
                        # Extract restaurant numbers
                        import ast
                        numbers = ast.literal_eval(feedback.split(":", 1)[1])
                        # Filter restaurants_to_add to only include selected ones
                        selected = [result['restaurants_to_add'][i-1] for i in numbers if i <= len(result['restaurants_to_add'])]
                        result['restaurants_to_add'] = selected
                        approval = True

                    # If approved, manually update Google Sheets
                    if approval:
                        num_to_add = len(result['restaurants_to_add'])
                        print(f"\n[DEBUG] Approval granted - adding {num_to_add} restaurants...")

                        # Import and call update function directly
                        from agents.restaurant_list_agent import update_google_sheet
                        result['user_approval'] = True
                        result['user_feedback'] = feedback

                        # Call the update function
                        print("[DEBUG] Calling update_google_sheet function...")
                        try:
                            final_result = update_google_sheet(result)

                            # Check for errors in the result
                            errors = final_result.get('errors', [])
                            if errors:
                                print(f"\nAgent: Encountered errors while updating:")
                                for error in errors:
                                    print(f"  - {error}")
                                logger.error(f"Errors during update: {errors}")

                            # Count successful additions (num_to_add minus errors related to adding)
                            add_errors = [e for e in errors if "Failed to add" in e]
                            num_added = num_to_add - len(add_errors)

                            if num_added > 0:
                                print(f"\nAgent: Successfully updated your restaurant list! Added {num_added} restaurant{'s' if num_added != 1 else ''}.\n")
                                logger.info(f"Added {num_added} restaurants to list")
                            elif not errors:
                                print(f"\nAgent: No restaurants were added.\n")

                            state = final_result
                        except Exception as e:
                            print(f"\nAgent: Failed to update Google Sheets: {str(e)}\n")
                            logger.error(f"Exception in update_google_sheet: {e}", exc_info=True)
                            import traceback
                            traceback.print_exc()
                    else:
                        print("\nAgent: Update cancelled.\n")
                        logger.info("User cancelled update")
                        state = result
                else:
                    # No approval needed
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


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main application entry point.
    """
    parser = argparse.ArgumentParser(description="Date Night Reservation Agent")
    parser.add_argument(
        "--agent",
        choices=["restaurant-list", "reservation-booking"],
        default="restaurant-list",
        help="Which agent to run"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the API response cache and exit"
    )
    parser.add_argument(
        "--cache-stats",
        action="store_true",
        help="Show cache statistics and exit"
    )

    args = parser.parse_args()

    # Handle cache commands
    if args.clear_cache:
        print("Clearing API response cache...")
        result = clear_cache()
        print(f"Removed {result['files_removed']} cached files.")
        if result['errors'] > 0:
            print(f"Encountered {result['errors']} errors during cleanup.")
        return

    if args.cache_stats:
        stats = get_cache_stats()
        print("\n=== Cache Statistics ===")
        print(f"Enabled: {stats['enabled']}")
        print(f"TTL: {stats['ttl_hours']} hours")
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_kb']:.2f} KB")
        if stats['cache_types']:
            print("\nBy type:")
            for cache_type, info in stats['cache_types'].items():
                print(f"  {cache_type}: {info['files']} files ({info['size_kb']:.2f} KB)")
        print()
        return

    if args.agent == "restaurant-list":
        run_restaurant_list_cli()
    else:
        print(f"Agent '{args.agent}' not yet implemented.")


if __name__ == "__main__":
    main()
