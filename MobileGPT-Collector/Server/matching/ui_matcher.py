"""UI element matcher."""

import xml.etree.ElementTree as ET
from typing import Optional

from ..data.models import UIAttributes
from ..utils.xml_parser import (
    find_matching_node_from_attributes,
    extract_interactable_indexes,
)


class UIMatcher:
    """Matcher for UI elements."""

    def __init__(self, parsed_xml: str):
        self.parsed_xml = parsed_xml
        self.tree = ET.fromstring(parsed_xml)

    def find_matching_uis(self, ui_attributes: UIAttributes) -> list[ET.Element]:
        return find_matching_node_from_attributes(self.tree, ui_attributes)

    def has_match(self, ui_attributes: UIAttributes) -> bool:
        return len(self.find_matching_uis(ui_attributes)) > 0

    def get_matched_indexes(self, ui_attributes: UIAttributes) -> list[int]:
        matches = self.find_matching_uis(ui_attributes)
        return [int(node.get("index")) for node in matches if node.get("index") is not None]

    def get_all_interactable_indexes(self) -> list[int]:
        return extract_interactable_indexes(self.parsed_xml)

    def match_keyuis(self, keyuis: dict[str, list[UIAttributes]]) -> tuple[list[str], list[str], set[int]]:
        supported = []
        unsupported = []
        matched_indexes: set[int] = set()

        for subtask_name, ui_attrs_list in keyuis.items():
            found = False
            for ui_attrs in ui_attrs_list:
                matches = self.find_matching_uis(ui_attrs)
                if matches:
                    found = True
                    for node in matches:
                        index = node.get("index")
                        if index is not None:
                            matched_indexes.add(int(index))
                    break
            if found:
                supported.append(subtask_name)
            else:
                unsupported.append(subtask_name)
        return supported, unsupported, matched_indexes

    def get_remaining_indexes(self, matched_indexes: set[int]) -> list[int]:
        all_interactable = set(self.get_all_interactable_indexes())
        return sorted(list(all_interactable - matched_indexes))

    def find_element_by_index(self, index: int) -> Optional[ET.Element]:
        return self.tree.find(f".//*[@index='{index}']")
