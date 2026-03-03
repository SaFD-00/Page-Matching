"""Supervisor node - routes exploration flow."""
from loguru import logger


def supervisor_node(state: dict) -> dict:
    """Decide next step in exploration.

    Routing logic:
    1. If action is already set → done (return to server)
    2. If status is "exploration_complete" → done
    3. If is_new_screen is True → go to "discover"
    4. Otherwise → go to "explore_action"
    """
    action = state.get("action")
    status = state.get("status", "exploring")
    is_new_screen = state.get("is_new_screen", True)

    if action is not None:
        logger.debug(f"Action ready: {action.get('name')}")
        return {"_next": "finish"}

    if status == "exploration_complete":
        logger.info("Exploration complete")
        return {"_next": "finish"}

    if status == "error":
        logger.error(f"Error state: {state.get('error_message', '')}")
        return {"_next": "finish"}

    if is_new_screen:
        logger.debug("New screen detected → discover")
        return {"_next": "discover"}

    logger.debug("Continuing exploration → explore_action")
    return {"_next": "explore_action"}


def route_supervisor(state: dict) -> str:
    """Conditional routing function for the graph."""
    return state.get("_next", "explore_action")
