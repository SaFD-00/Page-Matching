"""KeyUI selection agent."""

import xml.etree.ElementTree as ET
from typing import Optional
from loguru import logger

from ..data.models import Subtask, UIAttributes
from ..utils.llm_client import LLMClient
from ..utils.xml_parser import get_ui_key_attrib, extract_interactable_indexes
from .prompts import keyui_prompt


class KeyUISelector:
    """Agent for selecting the best KeyUI from the full XML screen."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def select(self, subtask: Subtask, screen: str) -> tuple[int, UIAttributes]:
        system_prompt, user_prompt = keyui_prompt.get_prompts(
            subtask_name=subtask.name,
            subtask_description=subtask.description,
            screen=screen
        )
        response = self.llm_client.query_dict(system_prompt=system_prompt, user_prompt=user_prompt)
        selected_index = self._parse_selected_index(response, screen)
        ui_attrs = get_ui_key_attrib(selected_index, screen)
        return selected_index, UIAttributes(**ui_attrs)

    def _parse_selected_index(self, response: dict, screen: str) -> int:
        selected = response.get("selected_ui_index", response.get("selected_index"))
        if selected is not None:
            try:
                idx = int(selected)
                interactable = extract_interactable_indexes(screen)
                if idx in interactable:
                    return idx
                try:
                    tree = ET.fromstring(screen)
                    node = tree.find(f".//*[@index='{idx}']")
                    if node is not None:
                        return idx
                except ET.ParseError:
                    pass
            except (ValueError, TypeError):
                pass

        interactable = extract_interactable_indexes(screen)
        if interactable:
            return interactable[0]
        raise ValueError("Could not determine valid UI index from LLM response")

    def select_all(self, subtasks: list[Subtask], screen: str) -> dict[str, list[UIAttributes]]:
        keyuis = {}
        for subtask in subtasks:
            try:
                _, ui_attrs = self.select(subtask, screen)
                keyuis[subtask.name] = [ui_attrs]
            except Exception as e:
                logger.warning(f"Failed to select KeyUI for '{subtask.name}': {e}")
        return keyuis
