"""LangGraph state definition for the collector graph."""

from typing import Optional

from typing_extensions import TypedDict


class CollectorState(TypedDict, total=False):
    """State for the MobileGPT-Collector LangGraph.

    All fields are optional (total=False) so that partial state updates
    can be passed between graph nodes.
    """

    # Session
    app_name: str
    app_package: str
    data_dir: str
    threshold: float
    matching: str  # "keyui-mobilegpt", "embedding"
    vision_enabled: bool
    model: str
    reasoning_effort: str

    # Current screen
    raw_xml: str
    parsed_xml: str
    hierarchy_xml: str
    encoded_xml: str
    pretty_xml: str
    screenshot_path: str
    page_index: int  # global page counter

    # Exploration tracking
    visited_pages: list[int]
    explored_subtasks: dict  # {page_idx_str: [(subtask_name, trigger_ui_idx), ...]}
    unexplored_subtasks: dict  # {page_idx_str: [{"name": str, "ui_index": int}, ...]}
    subtask_graph: dict  # {page_idx_str: [(target_page, subtask_name), ...]}
    back_edges: dict  # {page_idx_str: [source_pages...]}
    traversal_path: list[int]
    navigation_plan: list  # [(page, action_type, subtask_name), ...]

    # Current action tracking
    last_explored_page_index: Optional[int]
    last_explored_subtask_name: Optional[str]
    last_explored_ui_index: Optional[int]
    last_action_was_back: bool
    last_back_from_page: Optional[int]

    # Bundle tracking
    page_index_to_bundle: dict  # {page_idx_str: bundle_num}

    # Current page subtasks and keyuis (set by discover)
    current_subtasks: list  # list of Subtask dicts
    current_keyuis: dict  # {subtask_name: [UIAttributes dicts]}

    # Memory pipeline
    memory_dir: str  # MobileGPT-V2 format memory directory

    # Output
    action: Optional[dict]  # Action to send to client: {"name": str, "parameters": dict}
    status: str  # "exploring", "exploration_complete", "error"
    is_new_screen: bool  # True if screen needs to go through discover
    error_message: str
