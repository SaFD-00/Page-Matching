"""Data models for MobileCollector system.

Ported from KeyUI's models.py with additions for exploration state management.
Removed evaluation-only models (ExperimentResult, PSAResult, EvaluationOutput).
"""

from pydantic import BaseModel, ConfigDict, Field


class UIAttributes(BaseModel):
    """UI element attributes (MobileGPT style)."""

    model_config = ConfigDict(populate_by_name=True)

    self_attrs: dict = Field(default_factory=dict, alias="self")
    parent: dict = Field(default_factory=dict)
    children: list[tuple[dict, int, int]] = Field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "self": self.self_attrs,
            "parent": self.parent,
            "children": self.children,
        }


class Subtask(BaseModel):
    """Subtask definition."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str
    description: str = ""
    parameters: dict[str, str] = Field(default_factory=dict)


class KeyUI(BaseModel):
    """KeyUI (Trigger UI) information."""

    subtask_name: str
    ui_index: int
    ui_attributes: UIAttributes


class PageKnowledge(BaseModel):
    """Page knowledge (built from all pages in same bundle_id)."""

    bundle_id: str
    app_name: str
    subtasks: list[Subtask] = Field(default_factory=list)
    keyuis: dict[str, list[UIAttributes]] = Field(default_factory=dict)
    extra_uis: list[UIAttributes] = Field(default_factory=list)

    def get_all_subtask_names(self) -> list[str]:
        """Get all subtask names."""
        return [s.name for s in self.subtasks]


class MatchResult(BaseModel):
    """Matching result."""

    query_page_id: str
    candidate_bundle_id: str
    match_type: str  # EQSET, SUPERSET, SUBSET, NEW
    supported_subtasks: list[str] = Field(default_factory=list)
    match_ratio: float = 0.0
    threshold: float = 1.0
    remaining_ui_indexes: list[int] = Field(default_factory=list)

    def is_match(self) -> bool:
        """Check if this is considered a successful match."""
        return (
            self.match_type != "NEW"
            and len(self.supported_subtasks) >= 1
            and self.match_ratio >= self.threshold
        )


# --- MobileCollector-specific models ---


class BundleInfo(BaseModel):
    """Bundle metadata."""

    bundle_id: str
    bundle_num: int
    app_name: str
    pages: list[int] = Field(default_factory=list)
    representative_page: int = 0
    subtasks: list[Subtask] = Field(default_factory=list)
    keyuis: dict[str, list[UIAttributes]] = Field(default_factory=dict)


class PageData(BaseModel):
    """Stored page data."""

    app_name: str
    bundle_num: int
    page_num: int
    raw_xml_path: str = ""
    parsed_xml_path: str = ""
    hierarchy_xml_path: str = ""
    encoded_xml_path: str = ""
    pretty_xml_path: str = ""
    screenshot_path: str = ""
    subtasks: list[Subtask] = Field(default_factory=list)
    keyuis: dict[str, list[UIAttributes]] = Field(default_factory=dict)


class ExplorationState(BaseModel):
    """Exploration state for persistence."""

    app_name: str
    algorithm: str = "GREEDY"
    threshold: float = 1.0
    vision_enabled: bool = True
    visited_pages: list[int] = Field(default_factory=list)
    explored_subtasks: dict[str, list[list]] = Field(default_factory=dict)
    unexplored_subtasks: dict[str, list[dict]] = Field(default_factory=dict)
    traversal_path: list[int] = Field(default_factory=list)
    navigation_plan: list = Field(default_factory=list)
    subtask_graph: dict = Field(default_factory=dict)
    back_edges: dict[str, list[int]] = Field(default_factory=dict)
    bundle_count: int = 0
    total_pages_collected: int = 0
    page_counter: int = 0
    last_action_was_back: bool = False
    last_back_from_page: int | None = None
    last_explored_page_index: int | None = None
    last_explored_subtask_name: str | None = None
    last_explored_ui_index: int | None = None
    page_index_to_bundle: dict[str, int] = Field(default_factory=dict)
    started_at: str = ""
    last_updated: str = ""
