"""KeyUI V1 matching strategy (MobileGPT NodeManager approach)."""

import json
import xml.etree.ElementTree as ET
from typing import Optional
from loguru import logger

from ..data.models import MatchResult
from ..utils.xml_parser import find_matching_node
from .base import MatchingStrategy
from .page_registry import PageRegistry


class KeyUIV1Strategy(MatchingStrategy):
    """Original MobileGPT's NodeManager KeyUI matching strategy.

    Uses trigger_ui/extra_ui based structural matching.
    All trigger UIs for a subtask must be found for it to be "supported".
    Match types: EQSET (100% match, no remaining), SUBSET (partial, no remaining),
    SUPERSET (>=threshold match, has remaining), NEW (below threshold).
    """

    def __init__(self, match_threshold: float = 0.7):
        self.match_threshold = match_threshold

    @property
    def name(self) -> str:
        return "keyui-mobilegpt"

    def find_best_match(
        self,
        parsed_xml: str,
        hierarchy_xml: str,
        query_page_id: str,
        page_registry: PageRegistry,
    ) -> Optional[MatchResult]:
        tree = ET.fromstring(parsed_xml)

        best_result: Optional[MatchResult] = None
        best_supported_count = 0

        for bundle_id in page_registry.get_all_bundle_ids():
            page_knowledge = page_registry.get(bundle_id)
            if page_knowledge is None:
                continue

            result = self._match_node(tree, parsed_xml, bundle_id, page_knowledge, query_page_id)

            if result.match_type == "EQSET":
                return result  # Perfect match

            if result.match_type != "NEW":
                supported_count = len(result.supported_subtasks)
                if supported_count > best_supported_count:
                    best_result = result
                    best_supported_count = supported_count

        return best_result

    def _match_node(self, tree, parsed_xml, bundle_id, page_knowledge, query_page_id) -> MatchResult:
        """Match current screen against a stored page node (V1 NodeManager logic)."""
        keyuis = page_knowledge.keyuis
        extra_uis = page_knowledge.extra_uis
        subtasks = page_knowledge.subtasks

        # Collect all interactable UI indexes from current screen
        remaining_indexes = set()
        for tag in ['input', 'button', 'checker']:
            for node in tree.findall(f".//{tag}"):
                index = node.attrib.get('index')
                if index is not None:
                    remaining_indexes.add(int(index))

        # Match trigger UIs per subtask
        # V1 difference: ALL trigger UIs for a subtask must be found
        supported = []
        not_supported = []

        for subtask_name, ui_attrs_list in keyuis.items():
            found_indexes = self._find_required_uis(tree, ui_attrs_list)
            if len(found_indexes) < len(ui_attrs_list):
                not_supported.append(subtask_name)
            else:
                supported.append(subtask_name)
                remaining_indexes -= set(found_indexes)

        # Match extra UIs (remove from remaining)
        for extra_ui in extra_uis:
            extra_req = extra_ui.to_dict()
            matches = find_matching_node(tree, extra_req)
            for node in matches:
                idx = node.attrib.get('index')
                if idx is not None:
                    remaining_indexes.discard(int(idx))

        # Determine match type
        num_remaining = len(remaining_indexes)
        total_subtasks = len(subtasks)
        pct_supported = len(supported) / total_subtasks if total_subtasks > 0 else 0.0

        if num_remaining == 0 and pct_supported == 1.0:
            match_type = "EQSET"
        elif num_remaining == 0 and pct_supported > 0:
            match_type = "SUBSET"
        elif num_remaining > 0 and pct_supported >= self.match_threshold:
            match_type = "SUPERSET"
        else:
            match_type = "NEW"

        return MatchResult(
            query_page_id=query_page_id,
            candidate_bundle_id=bundle_id,
            match_type=match_type,
            supported_subtasks=supported,
            match_ratio=pct_supported,
            threshold=self.match_threshold,
            remaining_ui_indexes=sorted(list(remaining_indexes)),
        )

    def _find_required_uis(self, tree, ui_attrs_list) -> list[int]:
        """Find required UI elements on the current screen (V1 style).

        Each UIAttributes in the list must be found for the subtask to be supported.
        """
        found_indexes = []
        for ui_attrs in ui_attrs_list:
            requirements = ui_attrs.to_dict()
            matches = find_matching_node(tree, requirements)
            for node in matches:
                idx = node.attrib.get('index')
                if idx is not None:
                    found_indexes.append(int(idx))
        return found_indexes
