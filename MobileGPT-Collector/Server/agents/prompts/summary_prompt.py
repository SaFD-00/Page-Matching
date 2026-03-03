"""Prompts for page summary generation."""


def get_prompts(encoded_xml: str, available_subtasks: list[dict]) -> list[dict]:
    """Build prompt messages for summary generation."""
    subtask_text = "\n".join(
        f"- {s.get('name', '')}: {s.get('description', '')}"
        for s in available_subtasks
    )

    system_prompt = (
        "You are a mobile app screen analyst. "
        "Describe what the page displays and what users can do on it. "
        "Focus on functionality, not visual appearance. "
        "Output 2-3 sentences, max 100 words."
    )

    user_prompt = (
        f"Screen XML:\n{encoded_xml}\n\n"
        f"Available subtasks:\n{subtask_text}\n\n"
        "Describe this page concisely."
    )

    return [
        {"role": "developer", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
