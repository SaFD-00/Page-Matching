"""Data models for MobileCollector."""

from typing import Optional
from pydantic import BaseModel, Field


class Subtask(BaseModel):
    """A high-level user action extracted from a screen."""
    name: str
    description: str = ""
    parameters: dict = Field(default_factory=dict)


class UIAttributes(BaseModel):
    """Key UI element attributes for matching."""
    self_attrs: dict = Field(default_factory=dict, alias="self")
    parent: dict = Field(default_factory=dict)
    children: list = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict:
        return {
            "self": self.self_attrs,
            "parent": self.parent,
            "children": self.children,
        }


class PageKnowledge(BaseModel):
    """Knowledge about a bundle of pages."""
    bundle_id: str
    app_name: str = ""
    subtasks: list[Subtask] = Field(default_factory=list)
    keyuis: dict[str, list[UIAttributes]] = Field(default_factory=dict)
    extra_uis: list[UIAttributes] = Field(default_factory=list)
    encoded_xmls: list[str] = Field(default_factory=list)


class BundleInfo(BaseModel):
    """Bundle metadata."""
    bundle_id: str
    bundle_num: int
    app_name: str = ""
    pages: list[int] = Field(default_factory=list)
    representative_page: int = 0
    subtasks: list[Subtask] = Field(default_factory=list)
    keyuis: dict[str, list[UIAttributes]] = Field(default_factory=dict)


class MatchResult(BaseModel):
    """Result of matching a page against a bundle."""
    query_page_id: str = ""
    candidate_bundle_id: str = ""
    match_type: str = "NEW"  # EQSET, SUBSET, SUPERSET, NEW
    supported_subtasks: list[str] = Field(default_factory=list)
    match_ratio: float = 0.0
    threshold: float = 1.0
    remaining_ui_indexes: list[int] = Field(default_factory=list)

    def is_match(self) -> bool:
        return (
            self.match_type not in ("NEW",)
            and self.match_ratio >= self.threshold
            and len(self.supported_subtasks) > 0
        )


class ExplorationState(BaseModel):
    """Serializable exploration state for resume."""
    app_name: str = ""
    threshold: float = 1.0
    visited_pages: list[int] = Field(default_factory=list)
    explored_subtasks: dict = Field(default_factory=dict)
    unexplored_subtasks: dict = Field(default_factory=dict)
    traversal_path: list[int] = Field(default_factory=list)
    subtask_graph: dict = Field(default_factory=dict)
    back_edges: dict = Field(default_factory=dict)
    page_index_to_bundle: dict = Field(default_factory=dict)
    page_counter: int = 0
    bundle_count: int = 0
    total_pages_collected: int = 0
    started_at: str = ""
    last_updated: str = ""
