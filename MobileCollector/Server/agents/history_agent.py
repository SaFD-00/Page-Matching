"""Action guideline and description generation agent."""

from typing import Optional
from loguru import logger

from ..utils.llm_client import LLMClient
from .prompts import history_prompt


class HistoryAgent:
    """Generates HOW-to guidelines and action descriptions."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm = llm_client or LLMClient()

    def generate_guidance(self, action: dict, screen_xml: str) -> str:
        """Generate HOW-to guideline for a single action."""
        logger.info("Generating action guidance")
        prompts = history_prompt.get_guidance_prompts(
            action=action,
            screen_xml=screen_xml,
        )
        try:
            response = self._llm.query(
                system_prompt=prompts[0]["content"],
                user_prompt=prompts[1]["content"],
                is_json=False,
            )
            return response.strip() if isinstance(response, str) else str(response)
        except Exception as e:
            logger.warning(f"Guidance generation failed: {e}")
            return ""

    def generate_description(
        self,
        before_xml: str,
        after_xml: str,
        action: dict,
    ) -> str:
        """Generate action description (WHY + WHAT changed)."""
        logger.info("Generating action description")
        prompts = history_prompt.get_description_prompts(
            before_xml=before_xml,
            after_xml=after_xml,
            action=action,
        )
        try:
            response = self._llm.query(
                system_prompt=prompts[0]["content"],
                user_prompt=prompts[1]["content"],
                is_json=False,
            )
            return response.strip() if isinstance(response, str) else str(response)
        except Exception as e:
            logger.warning(f"Description generation failed: {e}")
            return ""
