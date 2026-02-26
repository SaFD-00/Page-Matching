"""Tests for mobilecollector.utils.xml_parser."""

import xml.etree.ElementTree as ET

import pytest

from mobilecollector.utils.xml_parser import (
    extract_interactable_indexes,
    get_ui_key_attrib,
    parse_xml_safely,
    find_parent_node,
    find_children_with_attributes,
    match_conditions,
)
from mobilecollector.storage.encoder import reformat_xml, simplify_structure


# Build a sample parsed XML that has index attributes and known interactive elements.
SAMPLE_RAW_XML = '''<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" content-desc="" checkable="false" clickable="false" bounds="[0,0][1080,2400]">
    <node index="1" text="Search" resource-id="com.app/search_btn" class="android.widget.TextView" content-desc="" checkable="false" clickable="true" bounds="[0,100][540,200]" />
    <node index="2" text="" resource-id="com.app/input" class="android.widget.EditText" content-desc="Enter text" checkable="false" clickable="true" bounds="[0,200][1080,300]">Search here</node>
    <node index="3" text="" resource-id="" class="android.widget.ImageView" content-desc="Logo" checkable="false" clickable="false" bounds="[100,300][200,400]" important="true" />
    <node index="4" text="Accept" resource-id="chk" class="android.widget.CheckBox" content-desc="" checkable="true" checked="false" clickable="true" bounds="[0,400][100,500]" />
  </node>
</hierarchy>'''


def _get_parsed_xml():
    """Get parsed XML with semantic tags and index attributes."""
    reformatted = reformat_xml(SAMPLE_RAW_XML)
    simplified = simplify_structure(reformatted)
    return simplified


# ── extract_interactable_indexes ────────────────────────────────────────


class TestExtractInteractableIndexes:
    def test_returns_buttons_inputs_checkers(self):
        parsed = _get_parsed_xml()
        indexes = extract_interactable_indexes(parsed)
        # button (index=1 from clickable TextView), input (index=2), checker (index=4)
        assert 1 in indexes
        assert 2 in indexes
        assert 4 in indexes

    def test_non_interactable_excluded(self):
        parsed = _get_parsed_xml()
        indexes = extract_interactable_indexes(parsed)
        # ImageView index=3 is not clickable, so should NOT be in the list
        assert 3 not in indexes

    def test_sorted_output(self):
        parsed = _get_parsed_xml()
        indexes = extract_interactable_indexes(parsed)
        assert indexes == sorted(indexes)

    def test_simple_button_only(self):
        xml = '<div><button index="5" bounds="[0,0][50,50]" /></div>'
        indexes = extract_interactable_indexes(xml)
        assert indexes == [5]


# ── get_ui_key_attrib ─────────────────────────────────────────────────


class TestGetUiKeyAttrib:
    def test_returns_self_parent_children(self):
        parsed = _get_parsed_xml()
        result = get_ui_key_attrib(1, parsed)
        assert "self" in result
        assert "parent" in result
        assert "children" in result

    def test_self_has_tag(self):
        parsed = _get_parsed_xml()
        result = get_ui_key_attrib(1, parsed)
        # index=1 is the Search button
        assert result["self"]["tag"] == "button"

    def test_missing_index_returns_empty(self):
        parsed = _get_parsed_xml()
        result = get_ui_key_attrib(999, parsed)
        assert result["self"] == {}
        assert result["parent"] == {}
        assert result["children"] == []

    def test_include_desc_false(self):
        parsed = _get_parsed_xml()
        result = get_ui_key_attrib(1, parsed, include_desc=False)
        assert "description" not in result["self"]


# ── parse_xml_safely ──────────────────────────────────────────────────


class TestParseXmlSafely:
    def test_valid_xml(self):
        result = parse_xml_safely("<root><child /></root>")
        assert result is not None
        assert result.tag == "root"

    def test_invalid_xml_returns_none(self):
        result = parse_xml_safely("<not>valid xml<<<")
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_xml_safely("")
        assert result is None


# ── find_parent_node ───────────────────────────────────────────────────


class TestFindParentNode:
    def test_finds_parent(self):
        xml = '<div index="0"><button index="1" /><input index="2" /></div>'
        tree = ET.fromstring(xml)
        rank, parent = find_parent_node(tree, 2)
        assert parent is not None
        assert parent.tag == "div"
        assert rank == 1  # input is second child (rank=1)

    def test_not_found(self):
        xml = '<div index="0"><button index="1" /></div>'
        tree = ET.fromstring(xml)
        rank, parent = find_parent_node(tree, 99)
        assert parent is None
        assert rank == 0


# ── match_conditions ──────────────────────────────────────────────────


class TestMatchConditions:
    def test_tag_match(self):
        node = ET.Element("button", {"id": "ok"})
        assert match_conditions(node, {"tag": "button"}) is True

    def test_tag_no_match(self):
        node = ET.Element("input", {"id": "ok"})
        assert match_conditions(node, {"tag": "button"}) is False

    def test_text_from_attrib(self):
        node = ET.Element("p", {"text": "hello"})
        assert match_conditions(node, {"text": "hello"}) is True

    def test_text_from_element_text(self):
        node = ET.Element("p")
        node.text = "world"
        assert match_conditions(node, {"text": "world"}) is True

    def test_none_value_skipped(self):
        node = ET.Element("button")
        assert match_conditions(node, {"tag": "button", "id": "NONE"}) is True
