"""KeyUI selection prompts."""


def get_system_prompt() -> str:
    return """You are a UI analysis assistant. Given a subtask and a mobile app screen, select the single most representative UI element (KeyUI) that triggers this subtask.

KeyUI Selection Criteria:
1. Functional Relevance: The UI must directly trigger or enable the subtask
2. Uniqueness: The UI should be distinctive to this subtask
3. Stability: The UI should appear consistently across similar screens
4. Identifiability: The UI should have clear attributes (id, description, text)

Prefer UIs with:
- Unique 'id' attributes (not 'NONE')
- Descriptive text or description
- Interactable tag type (<button>, <input>, <checker>, <scroll>)
- Stable structural position

Avoid UIs with:
- Generic attributes (all 'NONE')
- Text that changes dynamically
- Non-interactable elements

IMPORTANT: You MUST select exactly ONE UI element by its 'index' attribute.

Response Format (JSON):
{
  "selected_ui_index": <index>,
  "reason": "Brief explanation of why this UI best represents the subtask"
}"""


def get_user_prompt(subtask_name: str, subtask_description: str, screen: str) -> str:
    return f"""Subtask: {subtask_name}
Description: {subtask_description}

Screen HTML (find the UI that triggers this subtask):
<screen>{screen}</screen>

Select the single best UI element (by index attribute) that represents this subtask.
Response:"""


def get_prompts(subtask_name: str, subtask_description: str, screen: str) -> tuple[str, str]:
    return get_system_prompt(), get_user_prompt(subtask_name, subtask_description, screen)
