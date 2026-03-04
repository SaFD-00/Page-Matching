"""Subtask extraction agent."""

from typing import Optional
from loguru import logger

from ..data.models import Subtask
from ..utils.llm_client import LLMClient
from .prompts import subtask_prompt


class SubtaskExtractor:
    """Agent for extracting subtasks from screen XML."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def extract(self, encoded_xml: str) -> list[Subtask]:
        system_prompt, user_prompt = subtask_prompt.get_prompts(encoded_xml)
        response = self.llm_client.query(system_prompt=system_prompt, user_prompt=user_prompt, is_json=True)

        subtasks = []
        subtask_list = self._extract_subtask_list(response)
        for item in subtask_list:
            try:
                subtask = Subtask(
                    name=item.get("name", "unknown"),
                    description=item.get("description", ""),
                    parameters=item.get("parameters", {})
                )
                subtasks.append(subtask)
            except Exception:
                continue
        return subtasks

    def _extract_subtask_list(self, response) -> list[dict]:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ["subtasks", "result", "results", "items", "data", "actions"]:
                if key in response and isinstance(response[key], list):
                    return response[key]
            return [response]
        return []

