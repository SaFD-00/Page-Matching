"""Expand prompts for SUPERSET new subtask extraction."""


def get_system_prompt() -> str:
    return """You are a smartphone assistant analyzing a mobile app screen.
The screen has been partially matched to a known page, but there are additional UI elements that don't match any known subtasks.

Your job is to identify NEW subtasks that can be performed using the remaining (unmatched) UI elements.

Response Format (JSON):
{"new_subtasks": [
  {
    "name": "<action_name>",
    "description": "<what this action does>",
    "parameters": {"<param_name>": "<question for this param>"}
  }
]}"""


def get_user_prompt(screen: str, existing_subtasks: list[dict], remaining_ui_indexes: list[int]) -> str:
    existing_str = "\n".join([f"- {s['name']}: {s['description']}" for s in existing_subtasks])
    return f"""Screen HTML:
<screen>{screen}</screen>

Already known subtasks:
{existing_str}

Remaining UI indexes (not matched to any known subtask): {remaining_ui_indexes}

Identify NEW subtasks for the remaining UI elements only.
Response:"""


def get_prompts(screen: str, existing_subtasks: list[dict], remaining_ui_indexes: list[int]) -> tuple[str, str]:
    return get_system_prompt(), get_user_prompt(screen, existing_subtasks, remaining_ui_indexes)
