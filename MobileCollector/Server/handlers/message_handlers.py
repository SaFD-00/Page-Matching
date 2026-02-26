"""Message handlers for Android client communication."""
import os
import socket
from loguru import logger

from ..agents.app_agent import AppAgent
from ..storage.encoder import parse_raw_xml, hierarchy_parse, create_encoded_xml, create_pretty_xml
from ..utils.network import (
    recv_text_line,
    recv_xml,
    recv_xml_with_packages,
    recv_screenshot,
    send_json_response,
)


class MessageHandler:
    """Handles TCP messages from Android client."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.app_agent = AppAgent(data_dir)

        # Per-connection state
        self.app_name = None
        self.app_package = None
        self.current_screenshot_path = None
        self._temp_dir = os.path.join(data_dir, "_temp")
        self._screen_count = 0

    def handle_app_message(self, client_socket: socket.socket) -> str:
        """Handle 'A' message - app package name.

        Returns: app_name
        """
        package_name = recv_text_line(client_socket)
        logger.info(f"Package: {package_name}")

        if not package_name:
            raise ValueError("Empty package name")

        self.app_agent.update_app_list([package_name])
        self.app_name = self.app_agent.get_app_name(package_name)
        self.app_package = package_name

        logger.info(f"App: {self.app_name} ({package_name})")
        return self.app_name

    def handle_screenshot_message(self, client_socket: socket.socket) -> str:
        """Handle 'S' message - screenshot.

        Returns: screenshot path
        """
        os.makedirs(self._temp_dir, exist_ok=True)
        save_path = os.path.join(self._temp_dir, f"screen_{self._screen_count}.jpg")
        self.current_screenshot_path = recv_screenshot(client_socket, save_path)
        logger.debug(f"Screenshot saved: {save_path}")
        return self.current_screenshot_path

    def handle_xml_message(self, client_socket: socket.socket) -> dict:
        """Handle 'X' message - screen XML (App_Auto_Explorer protocol).

        Reads top_pkg and target_pkg before XML data.

        Returns: dict with raw_xml, parsed_xml, hierarchy_xml, encoded_xml,
                 pretty_xml, top_pkg, target_pkg
        """
        os.makedirs(self._temp_dir, exist_ok=True)
        raw_xml, top_pkg, target_pkg = recv_xml_with_packages(
            client_socket, self._temp_dir, self._screen_count
        )

        # Parse XML through module-level encoder pipeline
        parsed_xml = parse_raw_xml(raw_xml)
        hierarchy_xml = hierarchy_parse(parsed_xml)
        encoded_xml = create_encoded_xml(parsed_xml)
        pretty_xml = create_pretty_xml(encoded_xml)

        self._screen_count += 1

        return {
            "raw_xml": raw_xml,
            "parsed_xml": parsed_xml,
            "hierarchy_xml": hierarchy_xml,
            "encoded_xml": encoded_xml,
            "pretty_xml": pretty_xml,
            "top_pkg": top_pkg,
            "target_pkg": target_pkg,
        }

    def handle_finish_message(self) -> None:
        """Handle 'F' message - finish signal."""
        logger.info("Finish signal received")

    def send_action(self, client_socket: socket.socket, action: dict) -> None:
        """Send action to client."""
        send_json_response(client_socket, action)
        logger.debug(f"Sent action: {action.get('name', 'unknown')}")

    def get_screenshot_path(self) -> str:
        """Get current screenshot path."""
        return self.current_screenshot_path or ""

    def reset(self):
        """Reset per-connection state."""
        self.app_name = None
        self.app_package = None
        self.current_screenshot_path = None
        self._screen_count = 0
