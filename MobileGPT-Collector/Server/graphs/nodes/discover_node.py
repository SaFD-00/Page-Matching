"""Discover node - processes new screens."""
from loguru import logger
from ...agents.subtask_extractor import SubtaskExtractor
from ...agents.keyui_selector import KeyUISelector
from ...agents.safety_filter import SafetyFilter
from ...agents.summary_agent import SummaryAgent
from ...memory.collector_memory import CollectorMemory
from ...memory.explore_memory import ExploreMemoryAdapter
from ...utils.llm_client import LLMClient


# Module-level singletons (initialized on first use)
_subtask_extractor = None
_keyui_selector = None
_safety_filter = None
_memory = None
_explore_memory = None
_summary_agent = None


def _get_components(state: dict):
    """Lazy-init components."""
    global _subtask_extractor, _keyui_selector, _safety_filter, _memory
    global _explore_memory, _summary_agent

    if _subtask_extractor is None:
        model = state.get("model", "gpt-5.2")
        reasoning = state.get("reasoning_effort", "medium")
        llm_client = LLMClient(model=model, reasoning_effort=reasoning)
        _subtask_extractor = SubtaskExtractor(llm_client=llm_client)
        _keyui_selector = KeyUISelector(llm_client=llm_client)
        _safety_filter = SafetyFilter()
        _summary_agent = SummaryAgent(llm_client=llm_client)

    if _memory is None:
        _memory = CollectorMemory(
            data_dir=state["data_dir"],
            app_name=state["app_name"],
            threshold=state.get("threshold", 1.0),
            matching=state.get("matching", "keyui-mobilegpt"),
        )
        _memory.initialize()

    if _explore_memory is None:
        memory_dir = state.get("memory_dir", "./memory")
        _explore_memory = ExploreMemoryAdapter(
            memory_dir=memory_dir,
            app_name=state["app_name"],
        )
        _explore_memory.initialize()

    return _subtask_extractor, _keyui_selector, _safety_filter, _memory


def discover_node(state: dict) -> dict:
    """Process a new screen - match, extract subtasks, store."""
    subtask_extractor, keyui_selector, safety_filter, memory = _get_components(state)

    raw_xml = state["raw_xml"]
    parsed_xml = state["parsed_xml"]
    encoded_xml = state["encoded_xml"]
    hierarchy_xml = state["hierarchy_xml"]
    pretty_xml = state["pretty_xml"]
    screenshot_path = state.get("screenshot_path", "")

    # Copy mutable state
    visited_pages = list(state.get("visited_pages", []))
    explored_subtasks = dict(state.get("explored_subtasks", {}))
    unexplored_subtasks = dict(state.get("unexplored_subtasks", {}))
    subtask_graph = dict(state.get("subtask_graph", {}))
    back_edges = dict(state.get("back_edges", {}))
    traversal_path = list(state.get("traversal_path", []))
    page_index_to_bundle = dict(state.get("page_index_to_bundle", {}))

    last_page = state.get("last_explored_page_index")
    last_subtask = state.get("last_explored_subtask_name")
    last_was_back = state.get("last_action_was_back", False)
    last_back_from = state.get("last_back_from_page")

    try:
        # 1. Extract subtasks from current screen
        subtasks = subtask_extractor.extract(encoded_xml)
        safe_subtasks, unsafe_subtasks = safety_filter.filter(subtasks)

        if unsafe_subtasks:
            unsafe_names = [s.name for s in unsafe_subtasks]
            logger.warning(f"Filtered unsafe subtasks: {unsafe_names}")

        # 2. Select KeyUIs for safe subtasks
        keyuis = keyui_selector.select_all(safe_subtasks, parsed_xml)

        # 3. Process screen through memory (match + store)
        page_index, bundle_num, page_num, match_result = memory.process_new_screen(
            raw_xml=raw_xml,
            screenshot_path=screenshot_path,
            subtasks=safe_subtasks,
            keyuis=keyuis,
            encoded_xml=encoded_xml,
            parsed_xml=parsed_xml,
            hierarchy_xml=hierarchy_xml,
            pretty_xml=pretty_xml,
        )

        # 4. Update tracking
        visited_pages.append(page_index)
        page_index_to_bundle[str(page_index)] = bundle_num

        # Update traversal path
        if last_was_back and last_back_from is not None:
            # Came back - pop from traversal path
            if traversal_path and traversal_path[-1] == last_back_from:
                traversal_path.pop()
                # Record back edge
                back_key = str(last_back_from)
                if back_key not in back_edges:
                    back_edges[back_key] = []
                if page_index not in back_edges[back_key]:
                    back_edges[back_key].append(page_index)
        else:
            traversal_path.append(page_index)

        # 5. Update subtask graph if there was a previous exploration
        if last_page is not None and last_subtask is not None and not last_was_back:
            page_key = str(last_page)
            if page_key not in subtask_graph:
                subtask_graph[page_key] = []
            # Add edge: last_page --(last_subtask)--> page_index
            edge = (page_index, last_subtask)
            if edge not in subtask_graph[page_key]:
                subtask_graph[page_key].append(edge)

            # Mark the subtask as explored
            if page_key not in explored_subtasks:
                explored_subtasks[page_key] = []
            explored_entry = (last_subtask, state.get("last_explored_ui_index"))
            if explored_entry not in explored_subtasks[page_key]:
                explored_subtasks[page_key].append(explored_entry)

            # Remove from unexplored
            if page_key in unexplored_subtasks:
                unexplored_subtasks[page_key] = [
                    s for s in unexplored_subtasks[page_key]
                    if s["name"] != last_subtask
                ]

        # 6. Set up unexplored subtasks for this new page
        page_idx_key = str(page_index)
        if page_idx_key not in unexplored_subtasks:
            # Get interactable UI indexes for each subtask's KeyUI
            unexplored_list = []
            for subtask in safe_subtasks:
                ui_attrs_list = keyuis.get(subtask.name, [])
                first_attrs = ui_attrs_list[0] if ui_attrs_list else None
                ui_index = _find_keyui_index(parsed_xml, first_attrs)
                unexplored_list.append({
                    "name": subtask.name,
                    "ui_index": ui_index,
                    "description": subtask.description,
                    "ui_attributes": first_attrs.to_dict() if first_attrs and hasattr(first_attrs, 'to_dict') else first_attrs,
                })
            unexplored_subtasks[page_idx_key] = unexplored_list

            if page_idx_key not in subtask_graph:
                subtask_graph[page_idx_key] = []

        match_type = match_result.match_type if match_result else "NEW"
        logger.info(
            f"Discovered page {page_index} (bundle {bundle_num}/{page_num}): "
            f"{match_type}, {len(safe_subtasks)} subtasks, "
            f"{len(unexplored_subtasks.get(page_idx_key, []))} unexplored"
        )

        # --- MobileGPT-V2 format memory pipeline ---
        try:
            # Build available_subtask dicts with trigger_ui_index
            avail_subtask_dicts = []
            trigger_uis_dict = {}
            for s in safe_subtasks:
                ui_attrs_list = keyuis.get(s.name, [])
                first_attrs = ui_attrs_list[0] if ui_attrs_list else None
                ui_idx = _find_keyui_index(parsed_xml, first_attrs)
                avail_subtask_dicts.append({
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                    "trigger_ui_index": ui_idx,
                    "exploration": "unexplored",
                })
                if first_attrs:
                    trigger_uis_dict[s.name] = first_attrs.to_dict() if hasattr(first_attrs, 'to_dict') else first_attrs

            _explore_memory.add_page(
                page_index=page_index,
                available_subtasks=avail_subtask_dicts,
                trigger_uis=trigger_uis_dict,
                extra_uis=[],
                parsed_xml=parsed_xml,
                hierarchy_xml=hierarchy_xml,
                encoded_xml=encoded_xml,
                screenshot_path=screenshot_path,
                raw_xml=raw_xml,
                pretty_xml=pretty_xml,
                screen_num=page_index,
            )

            # Generate and store summary
            summary = _summary_agent.generate_summary(
                encoded_xml=encoded_xml,
                available_subtasks=avail_subtask_dicts,
                screenshot_path=screenshot_path,
            )
            if summary:
                _explore_memory.update_summary(page_index, summary)

            # Add transition edge from previous page
            if last_page is not None and last_subtask is not None and not last_was_back:
                last_ui_idx = state.get("last_explored_ui_index", -1)
                _explore_memory.add_transition(
                    from_page=last_page,
                    to_page=page_index,
                    subtask_name=last_subtask,
                    trigger_ui_index=last_ui_idx,
                )
                _explore_memory.update_end_page(
                    page_index=last_page,
                    subtask_name=last_subtask,
                    trigger_ui_index=last_ui_idx,
                    end_page=page_index,
                )
        except Exception as e:
            logger.warning(f"ExploreMemory pipeline failed: {e}")

        # Save state
        from ...data.models import ExplorationState
        from datetime import datetime
        exploration_state = ExplorationState(
            app_name=state["app_name"],
            threshold=state.get("threshold", 1.0),
            visited_pages=visited_pages,
            explored_subtasks=explored_subtasks,
            unexplored_subtasks=unexplored_subtasks,
            traversal_path=traversal_path,
            subtask_graph=subtask_graph,
            back_edges=back_edges,
            page_index_to_bundle=page_index_to_bundle,
            page_counter=memory.get_page_counter(),
            bundle_count=memory.bundle_manager.bundle_count,
            total_pages_collected=memory.bundle_manager.total_pages,
            started_at=state.get("started_at", datetime.now().isoformat()),
        )
        memory.save_state(exploration_state)

        return {
            "page_index": page_index,
            "visited_pages": visited_pages,
            "explored_subtasks": explored_subtasks,
            "unexplored_subtasks": unexplored_subtasks,
            "subtask_graph": subtask_graph,
            "back_edges": back_edges,
            "traversal_path": traversal_path,
            "page_index_to_bundle": page_index_to_bundle,
            "current_subtasks": [s.model_dump() for s in safe_subtasks],
            "current_keyuis": {name: [ui.to_dict() for ui in attrs] for name, attrs in keyuis.items()},
            "is_new_screen": False,
            "last_explored_page_index": None,
            "last_explored_subtask_name": None,
            "last_explored_ui_index": None,
            "last_action_was_back": False,
            "last_back_from_page": None,
            "status": "exploring",
        }

    except Exception as e:
        logger.error(f"Discover failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "is_new_screen": False,
            "status": "error",
            "error_message": str(e),
        }


def _find_keyui_index(parsed_xml: str, ui_attrs) -> int:
    """Find UI element index in parsed XML matching UIAttributes."""
    if ui_attrs is None:
        return -1
    try:
        from ...matching.ui_matcher import UIMatcher
        from ...data.models import UIAttributes
        if isinstance(ui_attrs, dict):
            ui_attrs = UIAttributes(**ui_attrs)
        matcher = UIMatcher(parsed_xml)
        indexes = matcher.get_matched_indexes(ui_attrs)
        return indexes[0] if indexes else -1
    except Exception as e:
        logger.warning(f"_find_keyui_index failed: {e}")
        return -1


def reset_discover_state():
    """Reset module-level singletons (for testing or reconnection)."""
    global _subtask_extractor, _keyui_selector, _safety_filter, _memory
    global _explore_memory, _summary_agent
    _subtask_extractor = None
    _keyui_selector = None
    _safety_filter = None
    _memory = None
    _explore_memory = None
    _summary_agent = None
