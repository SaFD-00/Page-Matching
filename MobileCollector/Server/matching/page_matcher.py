"""Page matching engine."""

from typing import Optional
from loguru import logger

from ..data.models import MatchResult, PageKnowledge, Subtask, UIAttributes
from ..utils.llm_client import LLMClient
from ..agents.prompts import expand_prompt
from .page_registry import PageRegistry
from .ui_matcher import UIMatcher


class PageMatcher:
    """Engine for matching pages to known pages."""

    def __init__(self, page_registry: PageRegistry, threshold: float = 1.0, llm_client: Optional[LLMClient] = None):
        self.registry = page_registry
        self.threshold = threshold
        self.llm_client = llm_client

    def match(self, query_parsed_xml: str, candidate_bundle_id: str, query_page_id: str = "") -> MatchResult:
        page_knowledge = self.registry.get(candidate_bundle_id)
        if page_knowledge is None:
            return MatchResult(query_page_id=query_page_id, candidate_bundle_id=candidate_bundle_id, match_type="NEW", threshold=self.threshold)

        ui_matcher = UIMatcher(query_parsed_xml)
        query_ui_indexes = set(ui_matcher.get_all_interactable_indexes())
        supported, unsupported, matched_indexes = ui_matcher.match_keyuis(page_knowledge.keyuis)
        remaining_indexes = query_ui_indexes - matched_indexes

        total_subtasks = len(page_knowledge.subtasks)
        match_ratio = len(supported) / total_subtasks if total_subtasks > 0 else 0.0
        num_remaining = len(remaining_indexes)

        if num_remaining == 0 and match_ratio == 1.0:
            match_type = "EQSET"
        elif num_remaining == 0 and match_ratio > 0:
            match_type = "SUBSET"
        elif num_remaining > 0 and match_ratio >= self.threshold:
            match_type = "SUPERSET"
        else:
            match_type = "NEW"

        return MatchResult(
            query_page_id=query_page_id, candidate_bundle_id=candidate_bundle_id,
            match_type=match_type, supported_subtasks=supported, match_ratio=match_ratio,
            threshold=self.threshold, remaining_ui_indexes=sorted(list(remaining_indexes))
        )

    def match_all_candidates(self, query_parsed_xml: str, query_page_id: str = "") -> list[MatchResult]:
        return [self.match(query_parsed_xml, bid, query_page_id) for bid in self.registry.get_all_bundle_ids()]

    def find_best_match(self, query_parsed_xml: str, query_page_id: str = "") -> Optional[MatchResult]:
        results = self.match_all_candidates(query_parsed_xml, query_page_id)
        good_matches = [r for r in results if r.is_match()]
        if not good_matches:
            return None
        type_priority = {"EQSET": 0, "SUPERSET": 1, "SUBSET": 2, "NEW": 3}
        good_matches.sort(key=lambda r: (type_priority.get(r.match_type, 3), -r.match_ratio))
        return good_matches[0]

    def extract_new_subtasks(self, query_encoded_xml: str, match_result: MatchResult) -> list[Subtask]:
        if match_result.match_type != "SUPERSET" or not match_result.remaining_ui_indexes:
            return []
        if self.llm_client is None:
            self.llm_client = LLMClient()

        bundle = self.registry.get(match_result.candidate_bundle_id)
        existing_subtasks = [{"name": s.name, "description": s.description} for s in bundle.subtasks] if bundle else []

        system_prompt, user_prompt = expand_prompt.get_prompts(
            screen=query_encoded_xml, existing_subtasks=existing_subtasks,
            remaining_ui_indexes=match_result.remaining_ui_indexes
        )
        try:
            response = self.llm_client.query(system_prompt=system_prompt, user_prompt=user_prompt, is_json=True)
            subtask_list = response if isinstance(response, list) else response.get("new_subtasks", response.get("subtasks", [response] if isinstance(response, dict) else []))
            return [Subtask(name=item.get("name", "unknown"), description=item.get("description", ""), parameters=item.get("parameters", {})) for item in subtask_list]
        except Exception as e:
            logger.warning(f"Failed to extract new subtasks: {e}")
            return []

    def set_threshold(self, threshold: float) -> None:
        self.threshold = threshold
