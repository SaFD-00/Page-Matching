"""Page matching engine."""

from typing import Optional
from loguru import logger

from ..data.models import MatchResult, PageKnowledge, Subtask, UIAttributes
from ..utils.llm_client import LLMClient
from ..utils.embedding import DescriptionEmbeddingCache, cosine_similarity
from ..agents.prompts import expand_prompt
from ..config import DEFAULT_DESC_SIMILARITY_THRESHOLD
from .page_registry import PageRegistry
from .ui_matcher import UIMatcher


class PageMatcher:
    """Engine for matching pages to known pages."""

    def __init__(
        self,
        page_registry: PageRegistry,
        threshold: float = 1.0,
        subtask_threshold: float = 0.7,
        desc_threshold: float = DEFAULT_DESC_SIMILARITY_THRESHOLD,
        llm_client: Optional[LLMClient] = None,
        embedding_cache: Optional[DescriptionEmbeddingCache] = None,
    ):
        self.registry = page_registry
        self.threshold = threshold
        self.subtask_threshold = subtask_threshold
        self.desc_threshold = desc_threshold
        self.llm_client = llm_client
        self._embedding_cache = embedding_cache or DescriptionEmbeddingCache()

    def match(
        self,
        query_parsed_xml: str,
        candidate_bundle_id: str,
        query_page_id: str = "",
        query_subtasks: Optional[list[Subtask]] = None,
    ) -> MatchResult:
        page_knowledge = self.registry.get(candidate_bundle_id)
        if page_knowledge is None:
            return MatchResult(query_page_id=query_page_id, candidate_bundle_id=candidate_bundle_id, match_type="NEW", threshold=self.threshold)

        ui_matcher = UIMatcher(query_parsed_xml)
        query_ui_indexes = set(ui_matcher.get_all_interactable_indexes())

        # Step A: KeyUI structural matching
        supported, unsupported, matched_indexes = ui_matcher.match_keyuis(page_knowledge.keyuis)

        # Step B: Description similarity verification
        demoted_subtasks = []
        description_similarities = {}

        if query_subtasks and supported:
            bundle_subtask_map = {s.name: s for s in page_knowledge.subtasks}
            query_descriptions = [s.description for s in query_subtasks if s.description]
            query_embeddings = self._embedding_cache.get_embeddings_batch(query_descriptions) if query_descriptions else []

            verified_supported = []
            demoted_indexes = set()

            for subtask_name in supported:
                bundle_subtask = bundle_subtask_map.get(subtask_name)
                if not bundle_subtask or not bundle_subtask.description:
                    verified_supported.append(subtask_name)
                    continue

                bundle_embedding = self._embedding_cache.get_embedding(bundle_subtask.description)
                if not bundle_embedding:
                    verified_supported.append(subtask_name)
                    continue

                best_similarity = 0.0
                for q_emb in query_embeddings:
                    if q_emb:
                        sim = cosine_similarity(bundle_embedding, q_emb)
                        best_similarity = max(best_similarity, sim)

                description_similarities[subtask_name] = best_similarity

                if best_similarity >= self.desc_threshold:
                    verified_supported.append(subtask_name)
                else:
                    demoted_subtasks.append(subtask_name)
                    unsupported.append(subtask_name)
                    subtask_indexes = ui_matcher.get_matched_indexes_for_subtask(
                        subtask_name, page_knowledge.keyuis
                    )
                    demoted_indexes.update(subtask_indexes)

            supported = verified_supported
            matched_indexes = matched_indexes - demoted_indexes

            if demoted_subtasks:
                logger.info(
                    f"Description verification: {len(verified_supported)} verified, "
                    f"{len(demoted_subtasks)} demoted for bundle={candidate_bundle_id}"
                )
                for name in demoted_subtasks:
                    sim = description_similarities.get(name, 0.0)
                    logger.debug(f"  Demoted '{name}': similarity={sim:.3f} < {self.desc_threshold}")

        # Step C: Match type determination (using verified results)
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
            threshold=self.threshold, remaining_ui_indexes=sorted(list(remaining_indexes)),
            demoted_subtasks=demoted_subtasks, description_similarities=description_similarities,
        )

    def match_all_candidates(
        self,
        query_parsed_xml: str,
        query_page_id: str = "",
        query_subtasks: Optional[list[Subtask]] = None,
    ) -> list[MatchResult]:
        return [
            self.match(query_parsed_xml, bid, query_page_id, query_subtasks)
            for bid in self.registry.get_all_bundle_ids()
        ]

    def find_best_match(
        self,
        query_parsed_xml: str,
        query_page_id: str = "",
        query_subtask_names: Optional[list[str]] = None,
        query_encoded_xml: Optional[str] = None,
        query_subtasks: Optional[list[Subtask]] = None,
    ) -> Optional[MatchResult]:
        # Step 1: KeyUI-based matching + description verification
        results = self.match_all_candidates(query_parsed_xml, query_page_id, query_subtasks)
        good_matches = [r for r in results if r.is_match()]
        if good_matches:
            type_priority = {"EQSET": 0, "SUPERSET": 1, "SUBSET": 2, "VARIANT": 3, "NEW": 4}
            good_matches.sort(key=lambda r: (type_priority.get(r.match_type, 4), -r.match_ratio))
            return good_matches[0]

        # Step 2: Subtask name overlap fallback (when all KeyUI matches are NEW)
        if query_subtask_names and query_encoded_xml:
            variant = self._find_subtask_variant(
                query_subtask_names, query_encoded_xml, query_page_id
            )
            if variant:
                return variant

        return None

    def _find_subtask_variant(
        self,
        query_subtask_names: list[str],
        query_encoded_xml: str,
        query_page_id: str,
    ) -> Optional[MatchResult]:
        """Fallback: find VARIANT match based on subtask name overlap + XML diff."""
        best_overlap = 0.0
        best_bundle_id = None

        query_set = set(query_subtask_names)

        for bundle_id in self.registry.get_all_bundle_ids():
            knowledge = self.registry.get(bundle_id)
            if knowledge is None:
                continue

            existing_names = {s.name for s in knowledge.subtasks}

            # Jaccard similarity: |A∩B| / |A∪B|
            intersection = existing_names & query_set
            union = existing_names | query_set
            overlap_ratio = len(intersection) / len(union) if union else 0.0

            if overlap_ratio >= self.subtask_threshold:
                # Must have XML diff to be VARIANT (not duplicate of exact same page)
                if not self.registry.has_identical_xml(bundle_id, query_encoded_xml):
                    if overlap_ratio > best_overlap:
                        best_overlap = overlap_ratio
                        best_bundle_id = bundle_id

        if best_bundle_id:
            knowledge = self.registry.get(best_bundle_id)
            supported = [s.name for s in knowledge.subtasks if s.name in query_set]
            logger.info(
                f"VARIANT match: bundle={best_bundle_id}, overlap={best_overlap:.2f}, "
                f"supported={len(supported)}/{len(query_set)}"
            )
            return MatchResult(
                query_page_id=query_page_id,
                candidate_bundle_id=best_bundle_id,
                match_type="VARIANT",
                supported_subtasks=supported,
                match_ratio=best_overlap,
                threshold=self.subtask_threshold,
                remaining_ui_indexes=[],
            )

        return None

    def extract_new_subtasks(self, query_encoded_xml: str, match_result: MatchResult) -> list[Subtask]:
        if match_result.match_type != "SUPERSET":
            return []
        if self.llm_client is None:
            self.llm_client = LLMClient()

        bundle = self.registry.get(match_result.candidate_bundle_id)
        existing_subtasks = [{"name": s.name, "description": s.description} for s in bundle.subtasks] if bundle else []
        excluded_names = [s.name for s in bundle.subtasks] if bundle else []

        system_prompt, user_prompt = expand_prompt.get_prompts(
            screen=query_encoded_xml, existing_subtasks=existing_subtasks,
            excluded_subtask_names=excluded_names,
        )
        try:
            response = self.llm_client.query(system_prompt=system_prompt, user_prompt=user_prompt, is_json=True)
            subtask_list = response if isinstance(response, list) else response.get("new_subtasks", response.get("subtasks", [response] if isinstance(response, dict) else []))
            return [Subtask(name=item.get("name", "unknown"), description=item.get("description", ""), parameters=item.get("parameters", {})) for item in subtask_list]
        except Exception as e:
            logger.warning(f"Failed to extract new subtasks: {e}")
            return []

