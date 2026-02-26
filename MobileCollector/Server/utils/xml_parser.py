"""XML parsing utilities for KeyUI system.

Based on MobileGPT's parsing_utils.py with modifications for KeyUI matching.
"""

import json
import xml.etree.ElementTree as ET
from typing import Optional

from ..data.models import UIAttributes


def find_parent_node(root: ET.Element, child_index: int) -> tuple[int, Optional[ET.Element]]:
    """Find the parent element of a child with a specific index.

    Args:
        root: The root element of the XML tree
        child_index: The index of the child element

    Returns:
        Tuple of (rank, parent_element) or (0, None) if not found
    """
    if isinstance(child_index, str):
        child_index = int(child_index)

    for parent in root.iter():
        for rank, child in enumerate(parent):
            child_idx = child.get("index")
            if child_idx is not None and int(child_idx) == child_index:
                return rank, parent

    return 0, None


def find_children_with_attributes(element: ET.Element, depth: int = 1) -> list[tuple[ET.Element, int, int]]:
    """Recursively find children with 'text' or 'description' attributes up to depth 3.

    Args:
        element: The current element to search within
        depth: The current depth in the tree

    Returns:
        List of tuples (child, depth, rank)
    """
    valid_children = []
    if depth > 3:
        return valid_children

    for rank, child in enumerate(element, start=0):
        # Check if child has text or description attribute
        if child.text is not None or 'description' in child.attrib:
            valid_children.append((child, depth, rank))
        # Recurse to find valid children
        valid_children.extend(find_children_with_attributes(child, depth + 1))

    return valid_children


def find_children_by_depth_and_rank(
    element: ET.Element,
    target_depth: int,
    target_rank: int,
    current_depth: int = 1
) -> list[ET.Element]:
    """Find children at a specific depth and rank.

    Args:
        element: The element to search within
        target_depth: Target depth level
        target_rank: Target rank (position among siblings)
        current_depth: Current depth level

    Returns:
        List of matching elements
    """
    matched_elements = []

    if current_depth == target_depth:
        try:
            matched_elements.append(element[target_rank])
        except IndexError:
            pass
    else:
        for child in element:
            matched_elements.extend(
                find_children_by_depth_and_rank(child, target_depth, target_rank, current_depth + 1)
            )

    return matched_elements


def match_conditions(node: ET.Element, condition: dict) -> bool:
    """Check if a node matches the given condition.

    Args:
        node: The node to check
        condition: Dictionary of conditions to match

    Returns:
        True if all conditions match
    """
    for key, value in condition.items():
        if value == 'NONE':
            continue

        if key == 'tag':
            if node.tag != value:
                return False
        elif key == 'class_name' or key == 'class':
            if node.attrib.get('class', 'NONE') != value:
                return False
        elif key == 'text':
            text = node.text
            if text is None:
                text = node.attrib.get('text', 'NONE')
            if text != value:
                return False
        else:
            if node.attrib.get(key, 'NONE') != value:
                return False

    return True


def find_matching_node(tree: ET.Element, requirements: dict) -> list[ET.Element]:
    """Find nodes in the tree that match specific requirements.

    Args:
        tree: The XML tree root
        requirements: Dictionary with 'self', 'parent', 'children' conditions

    Returns:
        List of matching nodes
    """
    matched_nodes = []

    def check_node(node: ET.Element, cur_parent: Optional[ET.Element] = None) -> Optional[ET.Element]:
        # Check self conditions
        if not match_conditions(node, requirements.get('self', {})):
            return None

        # Check parent conditions
        if cur_parent is not None and not match_conditions(cur_parent, requirements.get('parent', {})):
            return None

        # Check children conditions
        children_requirements = requirements.get('children', [])
        if children_requirements:
            matched_children = []
            for child_cond, child_depth, child_rank in children_requirements:
                children = find_children_by_depth_and_rank(node, child_depth, child_rank)
                for child in children:
                    if match_conditions(child, child_cond):
                        if child not in matched_children:
                            matched_children.append(child)
                            break

                if len(matched_children) != len(children_requirements):
                    return None

        return node

    for node in tree.iter():
        index = node.get("index")
        if index is not None:
            _, parent = find_parent_node(tree, int(index))
            result = check_node(node, cur_parent=parent)
            if result is not None:
                matched_nodes.append(result)

    return matched_nodes


def find_matching_node_from_attributes(tree: ET.Element, ui_attributes: UIAttributes) -> list[ET.Element]:
    """Find nodes matching UIAttributes.

    Args:
        tree: The XML tree root
        ui_attributes: UIAttributes object

    Returns:
        List of matching nodes
    """
    requirements = ui_attributes.to_dict()
    return find_matching_node(tree, requirements)


def get_ui_key_attrib(ui_index: int, screen: str, include_desc: bool = True) -> dict:
    """Get key attributes of a UI element.

    Args:
        ui_index: The UI element index
        screen: The XML screen content
        include_desc: Whether to include description attribute

    Returns:
        Dictionary with 'self', 'parent', 'children' attributes
    """
    tree = ET.fromstring(screen)

    node = tree.find(f".//*[@index='{ui_index}']")
    if node is None:
        return {"self": {}, "parent": {}, "children": []}

    # Self attributes
    its_attributes = {
        'tag': node.tag,
        'id': node.attrib.get('id', 'NONE'),
        'class': node.attrib.get('class', 'NONE')
    }
    if include_desc:
        its_attributes['description'] = node.attrib.get('description', 'NONE')

    # Parent attributes
    _, parent_node = find_parent_node(tree, ui_index)
    parent_attributes = {}
    if parent_node is not None:
        parent_attributes = {
            'tag': parent_node.tag,
            'id': parent_node.attrib.get('id', 'NONE'),
            'class': parent_node.attrib.get('class', 'NONE')
        }
        if include_desc:
            parent_attributes['description'] = parent_node.attrib.get('description', 'NONE')

    # Children attributes
    children = find_children_with_attributes(node)
    children_attributes_str = []
    for child_node, depth, rank in children:
        child_attribute = {
            'tag': child_node.tag,
            'id': child_node.attrib.get('id', 'NONE'),
            'class': child_node.attrib.get('class', 'NONE')
        }
        if include_desc:
            child_attribute['description'] = child_node.attrib.get('description', 'NONE')

        child_attribute_str = json.dumps((child_attribute, depth, rank))
        if child_attribute_str not in children_attributes_str:
            children_attributes_str.append(child_attribute_str)

    children_attributes = [json.loads(s) for s in children_attributes_str]

    return {"self": its_attributes, "parent": parent_attributes, "children": children_attributes}


def get_trigger_ui_attributes(trigger_ui_indexes: dict[str, list[int]], screen: str) -> dict[str, list[dict]]:
    """Get trigger UI attributes for all subtasks.

    Args:
        trigger_ui_indexes: Dictionary mapping subtask names to UI indexes
        screen: The XML screen content

    Returns:
        Dictionary mapping subtask names to lists of UI attributes
    """
    trigger_ui_data = {}

    for subtask_name, ui_indexes in trigger_ui_indexes.items():
        trigger_uis_attributes = []

        for ui_index in ui_indexes:
            ui_attributes = get_ui_key_attrib(int(ui_index), screen)

            # Skip duplicates based on self attributes
            skip = False
            new_self_str = json.dumps(ui_attributes['self'], sort_keys=True)
            for existing_attr in trigger_uis_attributes:
                existing_self_str = json.dumps(existing_attr['self'], sort_keys=True)
                if new_self_str == existing_self_str:
                    skip = True
                    break

            if not skip:
                trigger_uis_attributes.append(ui_attributes)

        trigger_ui_data[subtask_name] = trigger_uis_attributes

    return trigger_ui_data


def extract_interactable_indexes(screen: str) -> list[int]:
    """Extract indexes of interactable UI elements.

    Args:
        screen: The XML screen content

    Returns:
        List of interactable UI indexes
    """
    tree = ET.fromstring(screen)
    interactable_indexes = []

    # Interactable tags (based on MobileGPT's pretty XML format)
    interactable_tags = ['input', 'button', 'checker', 'scroll']

    for tag in interactable_tags:
        for node in tree.findall(f".//{tag}"):
            index = node.attrib.get('index')
            if index is not None:
                interactable_indexes.append(int(index))

    # Also check for clickable attribute
    for node in tree.iter():
        if node.attrib.get('clickable') == 'true':
            index = node.attrib.get('index')
            if index is not None:
                idx = int(index)
                if idx not in interactable_indexes:
                    interactable_indexes.append(idx)

    return sorted(interactable_indexes)


def get_extra_ui_attributes(trigger_ui_indexes: list[int], screen: str) -> list[dict]:
    """Get attributes of UI elements that are NOT trigger UIs.

    Args:
        trigger_ui_indexes: List of trigger UI indexes to exclude
        screen: The XML screen content

    Returns:
        List of UI attributes for extra (non-trigger) UIs
    """
    tree = ET.fromstring(screen)

    extra_ui_indexes = []
    for tag in ['input', 'button', 'checker']:
        for node in tree.findall(f".//{tag}"):
            index = node.attrib.get('index')
            if index is not None:
                idx = int(index)
                if idx not in trigger_ui_indexes:
                    extra_ui_indexes.append(idx)

    extra_ui_attributes = []
    for index in extra_ui_indexes:
        ui_attributes = get_ui_key_attrib(index, screen)
        extra_ui_attributes.append(ui_attributes)

    return extra_ui_attributes


def parse_xml_safely(xml_content: str) -> Optional[ET.Element]:
    """Safely parse XML content.

    Args:
        xml_content: XML string

    Returns:
        Parsed Element or None if parsing fails
    """
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError:
        return None


def get_all_ui_indexes(screen: str) -> list[int]:
    """Get all UI indexes from the screen.

    Args:
        screen: The XML screen content

    Returns:
        List of all UI indexes
    """
    tree = ET.fromstring(screen)
    indexes = []

    for node in tree.iter():
        index = node.attrib.get('index')
        if index is not None:
            indexes.append(int(index))

    return sorted(indexes)
