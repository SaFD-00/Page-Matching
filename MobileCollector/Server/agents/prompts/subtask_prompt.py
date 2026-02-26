"""Subtask extraction prompts."""


def get_system_prompt() -> str:
    return """You are a smartphone assistant to help users understand mobile app screens.
Given an HTML code of a mobile app screen delimited by <screen></screen>, your job is to list high-level functions (subtasks) that can be performed on this screen.

Each subtask should include:
1. name: Action name (general, not specific to this screen)
2. description: Brief description of what the action does
3. parameters: Information needed to execute (as questions)

***Guidelines***:
1. Read through the screen HTML code to grasp the overall intent
2. Identify interactable UI elements (<button>, <checker>, <input>, <scroll>)
3. Create a list of all possible subtasks based on interactable elements
4. Merge related actions into higher-level abstractions
   Example: 'input_name', 'input_email' -> 'fill_in_info'

***Constraints***:
1. Make actions GENERAL (e.g., 'call_contact' not 'call_Bob')
2. Use human-friendly parameter names (e.g., 'contact_name' not 'contact_index')
3. If parameter has few immutable options, list them

Response Format (JSON):
{"subtasks": [
  {
    "name": "<action_name>",
    "description": "<what this action does>",
    "parameters": {"<param_name>": "<question for this param>"}
  },
  ...
]}"""


def get_user_prompt(screen: str) -> str:
    return f"""HTML code of the mobile app screen:
<screen>{screen}</screen>

Extract all possible subtasks from this screen.
Response:"""


def get_prompts(screen: str) -> tuple[str, str]:
    return get_system_prompt(), get_user_prompt(screen)
