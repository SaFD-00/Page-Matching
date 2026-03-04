"""Message handlers for Android client communication."""
import os
import socket
from datetime import datetime
from loguru import logger

from ..agents.app_agent import AppAgent
from ..storage.encoder import parse_raw_xml, hierarchy_parse, create_encoded_xml, create_pretty_xml
from ..utils.network import (
    recv_text_line,
    recv_xml_with_packages,
    recv_screenshot,
    send_json_response,
)


class MessageHandler:
    """Handles TCP messages from Android client."""

    def __init__(self, data_dir: str, memory_dir: str = "./memory"):
        self.data_dir = data_dir
        self.memory_dir = memory_dir
        self.app_agent = AppAgent(data_dir)

        # Per-connection state
        self.app_name = None
        self.app_package = None
        self.current_screenshot_path = None
        self.log_directory = None
        self._screen_count = 0

    def _init_log_directory(self, app_name: str):
        """Create log directory: memory/log/{app_name}/hardcode/{datetime}/"""
        timestamp = datetime.now().strftime("%Y_%m_%d %H:%M:%S")
        self.log_directory = os.path.join(
            self.memory_dir, "log", app_name, "hardcode", timestamp
        )
        os.makedirs(os.path.join(self.log_directory, "screenshots"), exist_ok=True)
        os.makedirs(os.path.join(self.log_directory, "xmls"), exist_ok=True)
        logger.info(f"Log directory: {self.log_directory}")

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
        self._init_log_directory(self.app_name)

        logger.info(f"App: {self.app_name} ({package_name})")
        return self.app_name

    def handle_screenshot_message(self, client_socket: socket.socket) -> str:
        """Handle 'S' message - screenshot.

        Returns: screenshot path
        """
        screenshots_dir = os.path.join(self.log_directory, "screenshots")
        save_path = os.path.join(screenshots_dir, f"{self._screen_count}.jpg")
        self.current_screenshot_path = recv_screenshot(client_socket, save_path)
        logger.debug(f"Screenshot saved: {save_path}")
        return self.current_screenshot_path

    def handle_xml_message(self, client_socket: socket.socket) -> dict:
        """Handle 'X' message - screen XML (App_Auto_Explorer protocol).

        Reads top_pkg and target_pkg before XML data.
        Saves raw XML and 4 parsed variants to log_directory/xmls/.

        Returns: dict with raw_xml, parsed_xml, hierarchy_xml, encoded_xml,
                 pretty_xml, top_pkg, target_pkg
        """
        xmls_dir = os.path.join(self.log_directory, "xmls")
        raw_xml, top_pkg, target_pkg = recv_xml_with_packages(
            client_socket, xmls_dir, self._screen_count
        )

        # Parse XML through encoder pipeline
        parsed_xml = parse_raw_xml(raw_xml)
        hierarchy_xml = hierarchy_parse(parsed_xml)
        encoded_xml = create_encoded_xml(parsed_xml)
        pretty_xml = create_pretty_xml(encoded_xml)

        # Save parsed XML variants to xmls/
        idx = self._screen_count
        for suffix, content in [
            ("_parsed.xml", parsed_xml),
            ("_hierarchy_parsed.xml", hierarchy_xml),
            ("_encoded.xml", encoded_xml),
            ("_pretty.xml", pretty_xml),
        ]:
            with open(os.path.join(xmls_dir, f"{idx}{suffix}"), "w", encoding="utf-8") as f:
                f.write(content)

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

