"""Prompts for action guideline and description generation."""

import json


def get_guidance_prompts(action: dict, screen_xml: str) -> list[dict]:
    """Build prompt messages for HOW-to guideline generation."""
    system_prompt = (
        "You are a mobile app interaction guide. "
        "Describe HOW to perform the given action on the screen using visual cues. "
        "Use element descriptions like 'the magnifying glass icon' instead of technical indices. "
        "Output a single concise sentence."
    )

    user_prompt = (
        f"Screen XML:\n{screen_xml}\n\n"
        f"Action: {json.dumps(action)}\n\n"
        "Describe how to perform this action."
    )

    return [
        {"role": "developer", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def get_description_prompts(before_xml: str, after_xml: str, action: dict) -> list[dict]:
    """Build prompt messages for action description (WHY + WHAT changed)."""
    system_prompt = (
        "You are a mobile app action analyst. "
        "Explain WHY an action was performed and WHAT changed after it. "
        "Use a concise single sentence (max 50 words). "
        "Format: 'To [purpose], [action taken]; [result/change]'"
    )

    user_prompt = (
        f"Before XML:\n{before_xml}\n\n"
        f"After XML:\n{after_xml}\n\n"
        f"Action: {json.dumps(action)}\n\n"
        "Describe purpose and result."
    )

    return [
        {"role": "developer", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
