"""MobileCollector Server - KeyUI-based auto exploration."""
import os
import socket
import threading
from datetime import datetime
from loguru import logger

from .config import parse_args
from .utils.logging import setup_logging
from .utils.network import get_real_ip
from .handlers.message_handlers import MessageHandler
from .graphs.collector_graph import compile_collector_graph
from .graphs.nodes.discover_node import reset_discover_state
from .graphs.nodes.explore_action_node import reset_explore_action_state


class CollectorServer:
    """TCP server for MobileCollector auto exploration."""

    def __init__(self, port: int, data_dir: str, threshold: float,
                 model: str, vision: bool, reasoning_effort: str,
                 subtask_threshold: float = 0.7, memory_dir: str = "./memory"):
        self.port = port
        self.data_dir = data_dir
        self.threshold = threshold
        self.model = model
        self.vision = vision
        self.reasoning_effort = reasoning_effort
        self.subtask_threshold = subtask_threshold
        self.memory_dir = memory_dir
        self.buffer_size = 4096

        # Ensure directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(memory_dir, exist_ok=True)

    def start(self):
        """Start the server."""
        real_ip = get_real_ip()

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.port))
        server_socket.listen()

        logger.info(f"Server listening on {real_ip}:{self.port}")
        logger.info(f"Config: threshold={self.threshold}, model={self.model}, vision={self.vision}")

        try:
            while True:
                client_socket, client_address = server_socket.accept()
                logger.info(f"Client connected: {client_address}")
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            server_socket.close()

    def _handle_client(self, client_socket: socket.socket, client_address: tuple):
        """Handle a single client connection."""
        handler = MessageHandler(self.data_dir)
        graph = compile_collector_graph()

        # Reset node state for new connection
        reset_discover_state()
        reset_explore_action_state()

        graph_state = None
        exploration_active = False

        try:
            while True:
                raw_type = client_socket.recv(1)
                if not raw_type:
                    logger.info(f"Connection closed: {client_address}")
                    break

                msg_type = raw_type.decode()

                if msg_type == 'A':
                    # App package name
                    app_name = handler.handle_app_message(client_socket)

                    # Initialize graph state
                    graph_state = {
                        "app_name": app_name,
                        "app_package": handler.app_package,
                        "data_dir": self.data_dir,
                        "threshold": self.threshold,
                        "subtask_threshold": self.subtask_threshold,
                        "memory_dir": self.memory_dir,
                        "vision_enabled": self.vision,
                        "model": self.model,
                        "reasoning_effort": self.reasoning_effort,
                        "page_index": -1,
                        "visited_pages": [],
                        "explored_subtasks": {},
                        "unexplored_subtasks": {},
                        "subtask_graph": {},
                        "back_edges": {},
                        "traversal_path": [],
                        "navigation_plan": [],
                        "page_index_to_bundle": {},
                        "last_explored_page_index": None,
                        "last_explored_subtask_name": None,
                        "last_explored_ui_index": None,
                        "last_action_was_back": False,
                        "last_back_from_page": None,
                        "current_subtasks": [],
                        "current_keyuis": {},
                        "action": None,
                        "status": "exploring",
                        "is_new_screen": True,
                        "error_message": "",
                        "started_at": datetime.now().isoformat(),
                    }
                    exploration_active = True
                    logger.info(f"Exploration initialized for {app_name}")

                elif msg_type == 'S':
                    # Screenshot
                    handler.handle_screenshot_message(client_socket)

                elif msg_type == 'X':
                    # XML - run graph
                    if not exploration_active or graph_state is None:
                        logger.warning("XML received but no active exploration")
                        continue

                    xml_data = handler.handle_xml_message(client_socket)

                    top_pkg = xml_data.get("top_pkg", "")
                    target_pkg = xml_data.get("target_pkg", "")
                    logger.debug(f"top_pkg={top_pkg}, target_pkg={target_pkg}")

                    # External app detection: top_pkg differs from target app
                    if top_pkg and target_pkg and top_pkg != target_pkg:
                        logger.warning(
                            f"External app detected: top_pkg={top_pkg} != target_pkg={target_pkg}. "
                            "Sending back action."
                        )
                        handler.send_action(
                            client_socket, {"name": "back", "parameters": {}}
                        )
                        continue

                    # Update graph state with new screen data
                    graph_state.update(xml_data)
                    graph_state["screenshot_path"] = handler.get_screenshot_path()
                    graph_state["is_new_screen"] = True
                    graph_state["action"] = None  # Reset action for new invocation

                    # Run the graph
                    try:
                        result = graph.invoke(graph_state)

                        # Update graph state with results
                        graph_state.update(result)

                        # Send action to client
                        action = result.get("action")
                        if action:
                            handler.send_action(client_socket, action)

                            if action.get("name") == "finish":
                                logger.info("Exploration complete signal sent")
                                exploration_active = False
                        else:
                            logger.warning("No action returned from graph")

                        status = result.get("status", "exploring")
                        if status == "exploration_complete":
                            exploration_active = False
                            logger.info("Exploration complete")
                        elif status == "error":
                            logger.error(f"Graph error: {result.get('error_message', '')}")

                    except Exception as e:
                        logger.error(f"Graph execution error: {e}")
                        import traceback
                        traceback.print_exc()
                        # Send back action as fallback
                        handler.send_action(client_socket, {"name": "back", "parameters": {}})

                elif msg_type == 'F':
                    # Finish
                    handler.handle_finish_message()
                    exploration_active = False

                else:
                    logger.warning(f"Unknown message type: {msg_type}")

        except ConnectionError as e:
            logger.info(f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Client handler error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            client_socket.close()
            logger.info(f"Client disconnected: {client_address}")
