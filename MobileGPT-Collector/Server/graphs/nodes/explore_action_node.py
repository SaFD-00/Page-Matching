"""Explore action node - GREEDY algorithm for app exploration."""
import re
import xml.etree.ElementTree as ET
from collections import deque
from loguru import logger

from ...agents.history_agent import HistoryAgent
from ...utils.llm_client import LLMClient


# Module-level singletons
_history_agent = None


def _get_explore_components(state: dict):
    """Lazy-init history agent and get shared explore memory from discover_node."""
    global _history_agent
    if _history_agent is None:
        model = state.get("model", "gpt-5.4")
        reasoning = state.get("reasoning_effort", "medium")
        llm_client = LLMClient(model=model, reasoning_effort=reasoning)
        _history_agent = HistoryAgent(llm_client=llm_client)
    # Reuse the same ExploreMemoryAdapter instance from discover_node
    from .discover_node import _explore_memory
    return _history_agent, _explore_memory


def explore_action_node(state: dict) -> dict:
    """Determine next exploration action using GREEDY algorithm.

    GREEDY: BFS from current page to find nearest unexplored subtask.
    """
    history_agent, explore_memory = _get_explore_components(state)
    page_index = state["page_index"]
    unexplored = dict(state.get("unexplored_subtasks", {}))
    explored = dict(state.get("explored_subtasks", {}))
    subtask_graph = dict(state.get("subtask_graph", {}))
    back_edges = dict(state.get("back_edges", {}))
    traversal_path = list(state.get("traversal_path", []))
    navigation_plan = list(state.get("navigation_plan", []))
    parsed_xml = state.get("parsed_xml", "")

    page_key = str(page_index)

    # 1. If we have a navigation plan, execute next step
    if navigation_plan:
        step = navigation_plan[0]
        remaining_plan = navigation_plan[1:]

        target_page, action_type, subtask_name = step

        if action_type == "back":
            logger.debug(f"Navigation plan: back from {page_index}")
            return {
                "action": {"name": "back", "parameters": {}},
                "navigation_plan": remaining_plan,
                "last_action_was_back": True,
                "last_back_from_page": page_index,
                "is_new_screen": True,
            }
        else:
            # Forward action - find the trigger UI and click it
            ui_index = _find_subtask_ui_index(page_key, subtask_name, unexplored)
            if ui_index >= 0:
                action = _create_click_action(parsed_xml, ui_index, subtask_name)
                if action:
                    # Generate guideline and save to explore memory
                    try:
                        if history_agent and explore_memory:
                            guideline = history_agent.generate_guidance(action, parsed_xml)
                            explore_memory.mark_subtask_explored(
                                page_index=page_index,
                                subtask_name=subtask_name,
                                trigger_ui_index=ui_index,
                                action=action,
                                start_page=page_index,
                                end_page=-1,
                                parsed_xml=parsed_xml,
                                guideline=guideline,
                            )
                    except Exception as e:
                        logger.warning(f"ExploreMemory nav mark_explored failed: {e}")

                    return {
                        "action": action,
                        "navigation_plan": remaining_plan,
                        "last_explored_page_index": page_index,
                        "last_explored_subtask_name": subtask_name,
                        "last_explored_ui_index": ui_index,
                        "last_action_was_back": False,
                        "is_new_screen": True,
                    }

    # 2. Check if current page has unexplored subtasks
    current_unexplored = unexplored.get(page_key, [])
    if current_unexplored:
        # Explore the first unexplored subtask on current page
        subtask_info = current_unexplored[0]
        subtask_name = subtask_info["name"]
        ui_index = subtask_info.get("ui_index", -1)

        logger.info(f"Exploring subtask '{subtask_name}' (ui={ui_index}) on page {page_index}")

        action = _create_click_action(parsed_xml, ui_index, subtask_name)

        # Fallback: ui_index invalid → re-match using UIAttributes
        if action is None and ui_index < 0:
            ui_attrs_data = subtask_info.get("ui_attributes")
            if ui_attrs_data:
                fallback_index = _fallback_rematch(parsed_xml, ui_attrs_data)
                if fallback_index >= 0:
                    action = _create_click_action(parsed_xml, fallback_index, subtask_name)
                    if action:
                        ui_index = fallback_index
                        logger.info(f"Fallback matched ui_index {fallback_index} for '{subtask_name}'")

        if action:
            # Generate guideline and save to explore memory
            try:
                if history_agent and explore_memory:
                    guideline = history_agent.generate_guidance(action, parsed_xml)
                    explore_memory.mark_subtask_explored(
                        page_index=page_index,
                        subtask_name=subtask_name,
                        trigger_ui_index=ui_index,
                        action=action,
                        start_page=page_index,
                        end_page=-1,
                        parsed_xml=parsed_xml,
                        guideline=guideline,
                    )
                    if guideline:
                        explore_memory.update_guideline(
                            page_index=page_index,
                            subtask_name=subtask_name,
                            trigger_ui_index=ui_index,
                            guideline=guideline,
                        )
            except Exception as e:
                logger.warning(f"ExploreMemory mark_explored failed: {e}")

            return {
                "action": action,
                "navigation_plan": [],
                "last_explored_page_index": page_index,
                "last_explored_subtask_name": subtask_name,
                "last_explored_ui_index": ui_index,
                "last_action_was_back": False,
                "is_new_screen": True,
            }
        else:
            # Can't click this UI - mark as explored and try next
            logger.warning(f"Cannot click for '{subtask_name}' (ui_index={ui_index}), skipping")
            current_unexplored_updated = [s for s in current_unexplored if s["name"] != subtask_name]
            unexplored[page_key] = current_unexplored_updated

            # Mark as explored with -1 index
            if page_key not in explored:
                explored[page_key] = []
            explored[page_key].append((subtask_name, -1))

            return {
                "unexplored_subtasks": unexplored,
                "explored_subtasks": explored,
                "is_new_screen": False,  # Re-enter explore_action
            }

    # 3. No unexplored on current page - find nearest unexplored via BFS
    target = _find_nearest_unexplored(page_index, unexplored, subtask_graph, back_edges)

    if target is not None:
        target_page, target_subtask, path = target
        logger.info(f"GREEDY: Navigate from {page_index} to page {target_page} for '{target_subtask}' (path: {len(path)} steps)")

        if path:
            # Set navigation plan
            return {
                "navigation_plan": path,
                "is_new_screen": False,  # Re-enter supervisor → explore_action to execute plan
            }

    # 4. No reachable unexplored subtask - try going back
    if len(traversal_path) > 1:
        logger.debug(f"No unexplored reachable. Going back from {page_index}")
        return {
            "action": {"name": "back", "parameters": {}},
            "navigation_plan": [],
            "last_action_was_back": True,
            "last_back_from_page": page_index,
            "is_new_screen": True,
        }

    # 5. At root with nothing to explore - exploration complete
    logger.info("Exploration complete - all subtasks explored or unreachable")
    return {
        "status": "exploration_complete",
        "action": {"name": "finish", "parameters": {}},
    }


def _find_subtask_ui_index(page_key: str, subtask_name: str, unexplored: dict) -> int:
    """Find UI index for a subtask on a page."""
    for info in unexplored.get(page_key, []):
        if info["name"] == subtask_name:
            return info.get("ui_index", -1)
    return -1


def _create_click_action(parsed_xml: str, ui_index: int, subtask_name: str) -> dict | None:
    """Create a click action for a UI element by index."""
    if ui_index < 0:
        return None

    try:
        tree = ET.fromstring(parsed_xml)
        # Find element with matching index
        target = None
        for elem in tree.iter():
            idx = elem.get("index")
            if idx is not None and int(idx) == ui_index:
                target = elem
                break

        if target is None:
            return None

        bounds = target.get("bounds", "")
        if not bounds:
            return None

        # Parse bounds "[x1,y1][x2,y2]"
        matches = re.findall(r'\d+', bounds)
        if len(matches) < 4:
            return None

        x1, y1, x2, y2 = int(matches[0]), int(matches[1]), int(matches[2]), int(matches[3])
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        return {
            "name": "click",
            "parameters": {
                "index": ui_index,
                "x": center_x,
                "y": center_y,
                "description": f"Explore '{subtask_name}'"
            }
        }
    except Exception as e:
        logger.warning(f"Failed to create click action: {e}")
        return None


def _fallback_rematch(parsed_xml: str, ui_attrs_data) -> int:
    """Fallback: re-match UIAttributes against current screen."""
    try:
        from ...matching.ui_matcher import UIMatcher
        from ...data.models import UIAttributes
        if isinstance(ui_attrs_data, dict):
            ui_attrs_data = UIAttributes(**ui_attrs_data)
        matcher = UIMatcher(parsed_xml)
        indexes = matcher.get_matched_indexes(ui_attrs_data)
        return indexes[0] if indexes else -1
    except Exception as e:
        logger.warning(f"Fallback rematch failed: {e}")
        return -1


def _find_nearest_unexplored(
    current_page: int,
    unexplored: dict,
    subtask_graph: dict,
    back_edges: dict,
) -> tuple | None:
    """BFS from current page to find nearest page with unexplored subtasks.

    Returns: (target_page, target_subtask_name, path) or None
    path is list of (page, action_type, subtask_name) tuples
    """
    queue = deque()
    visited = {current_page}
    # (current_node, path_to_here)
    queue.append((current_page, []))

    while queue:
        node, path = queue.popleft()
        node_key = str(node)

        # Check if this node has unexplored subtasks (skip current if path is empty)
        if path:  # Don't check current page (already checked above)
            node_unexplored = unexplored.get(node_key, [])
            if node_unexplored:
                target_subtask = node_unexplored[0]["name"]
                return (node, target_subtask, path)

        # Expand forward edges
        for edge in subtask_graph.get(node_key, []):
            next_page, subtask_name = edge[0], edge[1]
            if next_page not in visited:
                visited.add(next_page)
                new_path = path + [(next_page, "forward", subtask_name)]
                queue.append((next_page, new_path))

        # Expand back edges
        for back_target in back_edges.get(node_key, []):
            if back_target not in visited:
                visited.add(back_target)
                new_path = path + [(back_target, "back", "")]
                queue.append((back_target, new_path))

    return None


def reset_explore_action_state():
    """Reset module-level singletons (for testing or reconnection)."""
    global _history_agent
    _history_agent = None
