"""Safety filter for dangerous subtasks."""

from loguru import logger

from ..data.models import Subtask
from ..config import UNSAFE_CATEGORIES


class SafetyFilter:
    """Filter dangerous subtasks based on predefined categories."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._unsafe_keywords = set()
        for keywords in UNSAFE_CATEGORIES.values():
            self._unsafe_keywords.update(k.lower() for k in keywords)

    def filter(self, subtasks: list[Subtask]) -> tuple[list[Subtask], list[Subtask]]:
        """Filter subtasks into safe and unsafe.

        Returns:
            Tuple of (safe_subtasks, unsafe_subtasks)
        """
        if not self.enabled:
            return subtasks, []

        safe = []
        unsafe = []
        for subtask in subtasks:
            if self._is_unsafe(subtask):
                logger.debug(f"Filtered unsafe subtask: {subtask.name}")
                unsafe.append(subtask)
            else:
                safe.append(subtask)
        return safe, unsafe

    def _is_unsafe(self, subtask: Subtask) -> bool:
        name_lower = subtask.name.lower()
        desc_lower = subtask.description.lower()

        for keyword in self._unsafe_keywords:
            if keyword in name_lower or keyword in desc_lower:
                return True
        return False
