"""
Prompts for parsing user edit commands.
"""

# System prompt for edit command parsing
EDIT_COMMAND_SYSTEM = (
    "You are a command parser for restaurant list management. Parse user "
    "requests into structured actions."
)


def edit_command_prompt(user_message: str) -> str:
    """
    Generate prompt for parsing natural language edit commands.

    Args:
        user_message: The user's edit command in natural language

    Returns:
        Formatted prompt string
    """
    return f"""Parse this user command into a structured action:

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
{{
  "action": "remove",
  "restaurant_name": "Restaurant X",
  "field": null,
  "new_value": null
}}"""
