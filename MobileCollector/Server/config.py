"""Configuration management for MobileCollector."""

import os
import argparse
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# Defaults
DEFAULT_PORT = 12345
DEFAULT_THRESHOLD = 1.0
DEFAULT_SUBTASK_THRESHOLD = 0.7
DEFAULT_MEMORY_DIR = "./memory"
DEFAULT_MODEL = "gpt-5.2"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_DATA_DIR = "./data"
DEFAULT_VISION = True

# LLM settings
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# Safety categories
UNSAFE_CATEGORIES = {
    "financial": ["pay", "purchase", "subscribe", "buy", "checkout", "transaction"],
    "account": ["login", "logout", "delete_account", "sign_in", "sign_up", "register"],
    "system": ["install", "uninstall", "reset", "format", "factory_reset"],
    "data": ["delete", "clear_all", "remove_all", "erase"],
    "communication": ["send", "compose", "post", "dial"],
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MobileCollector - KeyUI-based auto explorer")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help=f"KeyUI matching threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--vision", action="store_true", default=True, help="Enable vision mode (default)")
    parser.add_argument("--no-vision", dest="vision", action="store_false", help="Disable vision mode")
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR, help=f"Data directory (default: {DEFAULT_DATA_DIR})")
    parser.add_argument("--reasoning-effort", type=str, default=DEFAULT_REASONING_EFFORT, help="Reasoning effort (none, low, medium, high)")
    parser.add_argument("--subtask-threshold", type=float, default=DEFAULT_SUBTASK_THRESHOLD, help=f"Subtask overlap threshold for VARIANT matching (default: {DEFAULT_SUBTASK_THRESHOLD})")
    parser.add_argument("--memory-dir", type=str, default=DEFAULT_MEMORY_DIR, help=f"Memory directory for MobileGPT-V2 format (default: {DEFAULT_MEMORY_DIR})")
    return parser.parse_args()
