"""Collector exploration graph using LangGraph."""
from langgraph.graph import StateGraph, END
from loguru import logger

from .state import CollectorState
from .nodes.supervisor_node import supervisor_node, route_supervisor
from .nodes.discover_node import discover_node
from .nodes.explore_action_node import explore_action_node


def build_collector_graph() -> StateGraph:
    """Build the collector exploration graph.

    Graph topology:
        START → supervisor → (conditional)
                 ├── discover → supervisor
                 ├── explore_action → supervisor
                 └── finish → END
    """
    graph = StateGraph(CollectorState)

    # Add nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("discover", discover_node)
    graph.add_node("explore_action", explore_action_node)

    # Set entry point
    graph.set_entry_point("supervisor")

    # Add conditional edges from supervisor
    graph.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "discover": "discover",
            "explore_action": "explore_action",
            "finish": END,
        }
    )

    # discover and explore_action loop back to supervisor
    graph.add_edge("discover", "supervisor")
    graph.add_edge("explore_action", "supervisor")

    return graph


def compile_collector_graph():
    """Compile the graph for execution."""
    graph = build_collector_graph()
    return graph.compile()
