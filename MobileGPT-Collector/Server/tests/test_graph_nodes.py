"""Tests for mobilegpt_collector.graphs.nodes (supervisor and explore_action)."""

import pytest

from mobilegpt_collector.graphs.nodes.supervisor_node import supervisor_node, route_supervisor
from mobilegpt_collector.graphs.nodes.explore_action_node import explore_action_node


# ── supervisor_node ────────────────────────────────────────────────────


class TestSupervisorNode:
    def test_action_set_routes_to_finish(self):
        state = {"action": {"name": "click", "parameters": {}}}
        result = supervisor_node(state)
        assert result["_next"] == "finish"

    def test_exploration_complete_routes_to_finish(self):
        state = {"action": None, "status": "exploration_complete"}
        result = supervisor_node(state)
        assert result["_next"] == "finish"

    def test_error_routes_to_finish(self):
        state = {"action": None, "status": "error", "error_message": "oops"}
        result = supervisor_node(state)
        assert result["_next"] == "finish"

    def test_new_screen_routes_to_discover(self):
        state = {"action": None, "status": "exploring", "is_new_screen": True}
        result = supervisor_node(state)
        assert result["_next"] == "discover"

    def test_existing_screen_routes_to_explore_action(self):
        state = {"action": None, "status": "exploring", "is_new_screen": False}
        result = supervisor_node(state)
        assert result["_next"] == "explore_action"

    def test_default_status_and_new_screen(self):
        """With only action=None, defaults should route to discover."""
        state = {"action": None}
        result = supervisor_node(state)
        # status defaults to "exploring", is_new_screen defaults to True
        assert result["_next"] == "discover"


# ── route_supervisor ───────────────────────────────────────────────────


class TestRouteSupervisor:
    def test_routes_to_discover(self):
        assert route_supervisor({"_next": "discover"}) == "discover"

    def test_routes_to_explore_action(self):
        assert route_supervisor({"_next": "explore_action"}) == "explore_action"

    def test_routes_to_finish(self):
        assert route_supervisor({"_next": "finish"}) == "finish"

    def test_default_routes_to_explore_action(self):
        assert route_supervisor({}) == "explore_action"


# ── explore_action_node ────────────────────────────────────────────────

PARSED_XML_FOR_EXPLORE = (
    '<div index="0" bounds="[0,0][1080,2400]">'
    '<button index="1" id="search_btn" bounds="[0,100][540,200]" />'
    '<button index="2" id="settings_btn" bounds="[0,200][540,300]" />'
    '</div>'
)


class TestExploreActionNode:
    def test_explore_unexplored_on_current_page(self):
        """When current page has unexplored subtasks, explore the first one."""
        state = {
            "page_index": 0,
            "unexplored_subtasks": {
                "0": [
                    {"name": "search", "ui_index": 1, "description": "do search"},
                    {"name": "settings", "ui_index": 2, "description": "open settings"},
                ]
            },
            "explored_subtasks": {},
            "subtask_graph": {},
            "back_edges": {},
            "traversal_path": [0],
            "navigation_plan": [],
            "parsed_xml": PARSED_XML_FOR_EXPLORE,
        }
        result = explore_action_node(state)
        assert result["action"] is not None
        assert result["action"]["name"] == "click"
        assert result["last_explored_subtask_name"] == "search"
        assert result["last_explored_ui_index"] == 1

    def test_exploration_complete_when_nothing_left(self):
        """At root with nothing to explore -> exploration_complete."""
        state = {
            "page_index": 0,
            "unexplored_subtasks": {},
            "explored_subtasks": {},
            "subtask_graph": {},
            "back_edges": {},
            "traversal_path": [0],  # only root in path, len=1
            "navigation_plan": [],
            "parsed_xml": PARSED_XML_FOR_EXPLORE,
        }
        result = explore_action_node(state)
        assert result.get("status") == "exploration_complete"

    def test_go_back_when_no_unexplored_on_current_and_deep(self):
        """Deep in traversal with no unexplored anywhere -> go back."""
        state = {
            "page_index": 2,
            "unexplored_subtasks": {},
            "explored_subtasks": {},
            "subtask_graph": {},
            "back_edges": {},
            "traversal_path": [0, 1, 2],  # deep, len > 1
            "navigation_plan": [],
            "parsed_xml": PARSED_XML_FOR_EXPLORE,
        }
        result = explore_action_node(state)
        assert result["action"]["name"] == "back"
        assert result["last_action_was_back"] is True

    def test_execute_navigation_plan_back(self):
        """When navigation plan starts with a back step."""
        state = {
            "page_index": 1,
            "unexplored_subtasks": {"0": [{"name": "task", "ui_index": 1}]},
            "explored_subtasks": {},
            "subtask_graph": {},
            "back_edges": {},
            "traversal_path": [0, 1],
            "navigation_plan": [
                (0, "back", ""),
                (0, "forward", "task"),
            ],
            "parsed_xml": PARSED_XML_FOR_EXPLORE,
        }
        result = explore_action_node(state)
        assert result["action"]["name"] == "back"
        assert len(result["navigation_plan"]) == 1

    def test_skip_invalid_ui_index(self):
        """When ui_index cannot be clicked, skip and mark explored."""
        state = {
            "page_index": 0,
            "unexplored_subtasks": {
                "0": [{"name": "broken_task", "ui_index": -1}],
            },
            "explored_subtasks": {},
            "subtask_graph": {},
            "back_edges": {},
            "traversal_path": [0],
            "navigation_plan": [],
            "parsed_xml": PARSED_XML_FOR_EXPLORE,
        }
        result = explore_action_node(state)
        # Should not have an action (skipped), re-enters loop
        assert result.get("action") is None
        assert result["is_new_screen"] is False
        # Broken task should be removed from unexplored
        assert len(result["unexplored_subtasks"]["0"]) == 0
        # Should be marked explored
        assert len(result["explored_subtasks"]["0"]) == 1

    def test_bfs_navigation_to_remote_page(self):
        """When unexplored subtask is on a remote page, set navigation plan."""
        state = {
            "page_index": 0,
            "unexplored_subtasks": {
                "1": [{"name": "remote_task", "ui_index": 5}],
            },
            "explored_subtasks": {},
            "subtask_graph": {
                "0": [(1, "search")],
            },
            "back_edges": {},
            "traversal_path": [0],
            "navigation_plan": [],
            "parsed_xml": PARSED_XML_FOR_EXPLORE,
        }
        result = explore_action_node(state)
        # Should set a navigation plan to reach page 1
        assert "navigation_plan" in result
        assert len(result["navigation_plan"]) > 0
        assert result["is_new_screen"] is False
