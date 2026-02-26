"""Page data storage in MobileCollector format."""

import json
import os
from loguru import logger

from ..data.models import Subtask, UIAttributes


class PageStorage:
    """Saves page data in MobileCollector format."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def save_page(
        self,
        app_name: str,
        bundle_num: int,
        page_num: int,
        raw_xml: str,
        parsed_xml: str,
        hierarchy_xml: str,
        encoded_xml: str,
        pretty_xml: str,
        screenshot_path: str,
        subtasks: list[Subtask],
        keyuis: dict[str, list[UIAttributes]]
    ) -> str:
        """Save page data. Returns page directory path."""
        page_dir = os.path.join(self.data_dir, app_name, str(bundle_num), str(page_num))
        os.makedirs(page_dir, exist_ok=True)

        # Save XMLs
        self._write_file(os.path.join(page_dir, f"{page_num}.xml"), raw_xml)
        self._write_file(os.path.join(page_dir, f"{page_num}_parsed.xml"), parsed_xml)
        self._write_file(os.path.join(page_dir, f"{page_num}_hierarchy_parsed.xml"), hierarchy_xml)
        self._write_file(os.path.join(page_dir, f"{page_num}_encoded.xml"), encoded_xml)
        self._write_file(os.path.join(page_dir, f"{page_num}_pretty.xml"), pretty_xml)

        # Copy screenshot if it exists and isn't already in page_dir
        target_screenshot = os.path.join(page_dir, f"{page_num}.jpg")
        if screenshot_path and os.path.exists(screenshot_path) and screenshot_path != target_screenshot:
            import shutil
            shutil.copy2(screenshot_path, target_screenshot)

        # Save subtask.json
        subtask_data = [s.model_dump() for s in subtasks]
        self._write_json(os.path.join(page_dir, "subtask.json"), subtask_data)

        # Save keyui.json
        keyui_data = {name: [ui.to_dict() for ui in attrs] for name, attrs in keyuis.items()}
        self._write_json(os.path.join(page_dir, "keyui.json"), keyui_data)

        logger.debug(f"Saved page data: {app_name}/{bundle_num}/{page_num}")
        return page_dir

    def _write_file(self, path: str, content: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _write_json(self, path: str, data) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
