"""Page summary generation agent."""

from typing import Optional
from loguru import logger

from ..utils.llm_client import LLMClient
from .prompts import summary_prompt


class SummaryAgent:
    """Generates human-readable page summaries."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm = llm_client or LLMClient()

    def generate_summary(
        self,
        encoded_xml: str,
        available_subtasks: list[dict],
        screenshot_path: Optional[str] = None,
    ) -> str:
        """Generate page summary (max 100 words, 2-3 sentences)."""
        logger.info("Generating page summary")
        prompts = summary_prompt.get_prompts(
            encoded_xml=encoded_xml,
            available_subtasks=available_subtasks,
        )
        try:
            response = self._llm.query(
                system_prompt=prompts[0]["content"],
                user_prompt=prompts[1]["content"],
                is_json=False,
            )
            return response.strip() if isinstance(response, str) else str(response)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return ""
