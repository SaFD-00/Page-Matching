"""App agent for looking up app names from package names using SerpAPI."""

import csv
import os
from pathlib import Path

from loguru import logger
from serpapi import GoogleSearch  # from google-search-results package

from ..config import SERPAPI_KEY


class AppAgent:
    """Agent for managing app name <-> package name mappings.

    Uses SerpAPI Google Play Store search to resolve package names
    to human-readable app names, caching results in a CSV file.
    """

    CSV_COLUMNS = ["app_name", "package_name", "description"]

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.csv_path = os.path.join(data_dir, "apps.csv")
        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        """Create the CSV file with headers if it doesn't exist."""
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
                writer.writeheader()
            logger.info(f"Created apps CSV at {self.csv_path}")

    def _load_entries(self) -> list[dict]:
        """Load all entries from the CSV file."""
        entries: list[dict] = []
        try:
            with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append(row)
        except FileNotFoundError:
            logger.warning(f"CSV file not found: {self.csv_path}")
        return entries

    def _save_entry(self, app_name: str, package_name: str, description: str) -> None:
        """Append a single entry to the CSV file."""
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
            writer.writerow({
                "app_name": app_name,
                "package_name": package_name,
                "description": description,
            })

    def _is_known(self, package_name: str) -> bool:
        """Check if a package name already exists in the CSV."""
        entries = self._load_entries()
        return any(e["package_name"] == package_name for e in entries)

    def _search_app_info(self, package_name: str) -> tuple[str, str]:
        """Query SerpAPI Google Play Store for app info.

        Returns:
            Tuple of (app_name, description). Falls back to derived name on failure.
        """
        try:
            params = {
                "engine": "google_play_product",
                "product_id": package_name,
                "api_key": SERPAPI_KEY,
            }
            search = GoogleSearch(params)
            results = search.get_dict()
            title = results.get("product_info", {}).get("title", "")
            description = results.get("about_this_app", {}).get("snippet", "")
            if title:
                logger.info(f"SerpAPI resolved {package_name} -> {title}")
                return title, description
            else:
                logger.warning(f"SerpAPI returned no title for {package_name}, deriving from package name")
                return self._derive_app_name(package_name), ""
        except Exception as e:
            logger.error(f"SerpAPI search failed for {package_name}: {e}")
            return self._derive_app_name(package_name), ""

    @staticmethod
    def _derive_app_name(package_name: str) -> str:
        """Derive a human-readable app name from a package name.

        Example: "com.example.myapp" -> "myapp"
        """
        parts = package_name.split(".")
        return parts[-1] if parts else package_name

    def update_app_list(self, package_names: list[str]) -> None:
        """Update the app list with new package names.

        For each package name not already in the CSV, queries SerpAPI
        to resolve the app name and saves the result.
        """
        for package_name in package_names:
            if self._is_known(package_name):
                logger.debug(f"Package {package_name} already known, skipping")
                continue

            app_name, description = self._search_app_info(package_name)
            self._save_entry(app_name, package_name, description)
            logger.info(f"Added app entry: {app_name} ({package_name})")

    def get_app_name(self, package_name: str) -> str:
        """Look up the app name for a given package name.

        If not found in the CSV, derives the name from the package name.
        """
        entries = self._load_entries()
        for entry in entries:
            if entry["package_name"] == package_name:
                return entry["app_name"]

        logger.warning(f"Package {package_name} not found in CSV, deriving app name")
        return self._derive_app_name(package_name)

    def get_package_name(self, app_name: str) -> str:
        """Reverse lookup: find the package name for a given app name.

        Performs case-insensitive matching.

        Returns:
            The package name if found, otherwise an empty string.
        """
        entries = self._load_entries()
        app_name_lower = app_name.lower()
        for entry in entries:
            if entry["app_name"].lower() == app_name_lower:
                return entry["package_name"]

        logger.warning(f"App name '{app_name}' not found in CSV")
        return ""
