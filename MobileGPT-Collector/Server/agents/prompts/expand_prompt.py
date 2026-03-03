"""Expand prompts for SUPERSET new subtask extraction (Approach B)."""


def get_system_prompt() -> str:
    return """You are a smartphone assistant analyzing a mobile app screen.
The screen has been partially matched to a known page, but may contain additional functionality not yet captured.

Your job is to identify NEW subtasks from the full screen context, excluding any subtasks already known (listed in the exclusion list).

Guidelines:
- Use general, reusable action names (e.g., "search", "toggle_setting", "open_profile") rather than screen-specific names.
- Merge closely related actions into a single subtask when they serve the same purpose (e.g., don't split "tap search icon" and "type in search bar" — combine as "search").
- Each subtask should have a clear, distinct purpose.
- Include parameters only when user input is required (e.g., text to type, option to select).

Response Format (JSON):
{"new_subtasks": [
  {
    "name": "<action_name>",
    "description": "<what this action does>",
    "parameters": {"<param_name>": "<question for this param>"}
  }
]}"""


def get_user_prompt(screen: str, existing_subtasks: list[dict], excluded_subtask_names: list[str]) -> str:
    existing_str = "\n".join([f"- {s['name']}: {s['description']}" for s in existing_subtasks])
    exclusion_str = ", ".join(excluded_subtask_names) if excluded_subtask_names else "(none)"
    return f"""Screen HTML:
<screen>{screen}</screen>

Already known subtasks (exclusion list — do NOT extract these again):
{existing_str}

Excluded subtask names: [{exclusion_str}]

Analyze the ENTIRE screen and identify any NEW subtasks not in the exclusion list.
Response:"""


def get_prompts(screen: str, existing_subtasks: list[dict], excluded_subtask_names: list[str]) -> tuple[str, str]:
    return get_system_prompt(), get_user_prompt(screen, existing_subtasks, excluded_subtask_names)
