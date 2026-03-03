"""Network utilities for TCP communication with Android client."""

import json
import os
import socket
from typing import Optional, Tuple

from loguru import logger


def get_real_ip() -> str:
    """Get real IP address of the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def recv_text_line(client_socket: socket.socket) -> str:
    """Receive a text line ending with newline."""
    data = b''
    while not data.endswith(b'\n'):
        chunk = client_socket.recv(1)
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data.decode().strip()


def recv_binary_data(client_socket: socket.socket, buffer_size: int = 4096) -> bytes:
    """Receive binary data with size prefix."""
    file_size_str = recv_text_line(client_socket)
    file_size = int(file_size_str)

    data = b''
    bytes_remaining = file_size
    while bytes_remaining > 0:
        chunk = client_socket.recv(min(bytes_remaining, buffer_size))
        if not chunk:
            raise ConnectionError("Connection closed during data transfer")
        data += chunk
        bytes_remaining -= len(chunk)
    return data


def recv_xml(client_socket: socket.socket, save_dir: str, index: int, buffer_size: int = 4096) -> str:
    """Receive XML data from client and save raw XML."""
    raw_data = recv_binary_data(client_socket, buffer_size)
    raw_xml = raw_data.decode().strip().replace('class=""', 'class="unknown"')

    # Save raw XML
    os.makedirs(save_dir, exist_ok=True)
    raw_xml_path = os.path.join(save_dir, f"{index}.xml")
    with open(raw_xml_path, 'w', encoding='utf-8') as f:
        f.write(raw_xml)

    return raw_xml


def recv_xml_with_packages(
    client_socket: socket.socket,
    save_dir: str,
    index: int,
    buffer_size: int = 4096,
) -> Tuple[str, str, str]:
    """Receive XML with package info from App_Auto_Explorer protocol.

    Protocol format: top_package + '\\n' + target_package + '\\n' + size + '\\n' + xml_data

    Args:
        client_socket: Connected client socket.
        save_dir: Directory to save raw XML.
        index: Screen index for filename.
        buffer_size: Buffer size for binary read.

    Returns:
        Tuple of (raw_xml, top_pkg, target_pkg).
    """
    top_pkg = recv_text_line(client_socket)
    target_pkg = recv_text_line(client_socket)
    raw_data = recv_binary_data(client_socket, buffer_size)
    raw_xml = raw_data.decode().strip().replace('class=""', 'class="unknown"')

    os.makedirs(save_dir, exist_ok=True)
    raw_xml_path = os.path.join(save_dir, f"{index}.xml")
    with open(raw_xml_path, 'w', encoding='utf-8') as f:
        f.write(raw_xml)

    return raw_xml, top_pkg, target_pkg


def recv_screenshot(client_socket: socket.socket, save_path: str, buffer_size: int = 4096) -> str:
    """Receive screenshot from client and save."""
    image_data = recv_binary_data(client_socket, buffer_size)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'wb') as f:
        f.write(image_data)

    return save_path


def send_json_response(client_socket: socket.socket, data: dict) -> None:
    """Send JSON response to client."""
    response = json.dumps(data) + '\n'
    client_socket.sendall(response.encode())
