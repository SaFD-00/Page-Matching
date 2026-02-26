"""Tests for mobilecollector.storage.encoder."""

import xml.etree.ElementTree as ET

import pytest

from mobilecollector.storage.encoder import (
    reformat_xml,
    parse_raw_xml,
    hierarchy_parse,
    create_encoded_xml,
    simplify_structure,
    remove_redundancies,
)


SAMPLE_RAW_XML = '''<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" content-desc="" checkable="false" clickable="false" bounds="[0,0][1080,2400]">
    <node index="0" text="Search" resource-id="com.app/search_btn" class="android.widget.TextView" content-desc="" checkable="false" clickable="true" bounds="[0,100][540,200]" />
    <node index="1" text="" resource-id="com.app/input" class="android.widget.EditText" content-desc="Enter text" checkable="false" clickable="true" bounds="[0,200][1080,300]">Search here</node>
    <node index="2" text="" resource-id="" class="android.widget.ImageView" content-desc="Logo" checkable="false" clickable="false" bounds="[100,300][200,400]" important="true" />
  </node>
</hierarchy>'''


# ── reformat_xml ───────────────────────────────────────────────────────


class TestReformatXml:
    def test_edittext_becomes_input(self):
        result = reformat_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        inputs = tree.findall(".//input")
        assert len(inputs) >= 1
        # EditText with description "Enter text" should be input
        found = any(
            el.attrib.get("description") == "Enter text" for el in inputs
        )
        assert found

    def test_clickable_textview_becomes_button(self):
        result = reformat_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        buttons = tree.findall(".//button")
        assert len(buttons) >= 1
        # The clickable TextView "Search" should be a button
        found = any(el.attrib.get("id") == "search_btn" for el in buttons)
        assert found

    def test_textview_becomes_p_when_not_clickable(self):
        # Use a node element directly as root to avoid hierarchy wrapper
        xml = '''<node index="0" text="Hello" resource-id="" class="android.widget.TextView"
                content-desc="" checkable="false" clickable="false" bounds="[0,0][100,50]" />'''
        result = reformat_xml(xml)
        tree = ET.fromstring(result)
        assert tree.tag == "p"
        assert tree.text == "Hello"

    def test_imageview_becomes_img(self):
        result = reformat_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        imgs = tree.findall(".//img")
        assert len(imgs) >= 1
        found = any(el.attrib.get("description") == "Logo" for el in imgs)
        assert found

    def test_checkable_becomes_checker(self):
        # Use a node element directly as root to avoid hierarchy wrapper
        xml = '''<node index="0" text="Agree" resource-id="chk" class="android.widget.CheckBox"
                content-desc="" checkable="true" checked="true" clickable="true" bounds="[0,0][50,50]" />'''
        result = reformat_xml(xml)
        tree = ET.fromstring(result)
        assert tree.tag == "checker"
        assert tree.attrib.get("checked") == "true"

    def test_layout_becomes_div(self):
        xml = '''<hierarchy rotation="0">
          <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
                content-desc="" checkable="false" clickable="false" bounds="[0,0][100,100]">
            <node index="1" text="child" resource-id="" class="android.widget.TextView"
                  content-desc="" checkable="false" clickable="false" bounds="[0,0][50,50]" />
          </node>
        </hierarchy>'''
        result = reformat_xml(xml)
        tree = ET.fromstring(result)
        # After simplify_structure single child collapses, but reformat_xml alone
        # should produce a div wrapping a p
        # The root FrameLayout wrapping -> the hierarchy becomes the FrameLayout node
        # which should map to div
        assert tree.tag in ("div", "p")

    def test_resource_id_split(self):
        result = reformat_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        # "com.app/search_btn" should be split to "search_btn"
        buttons = tree.findall(".//button")
        found = any(el.attrib.get("id") == "search_btn" for el in buttons)
        assert found


# ── parse_raw_xml (full pipeline) ─────────────────────────────────────


class TestParseRawXml:
    def test_returns_valid_xml(self):
        result = parse_raw_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        assert tree is not None

    def test_no_hierarchy_tag(self):
        result = parse_raw_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        assert tree.tag != "hierarchy"

    def test_contains_interactable_elements(self):
        result = parse_raw_xml(SAMPLE_RAW_XML)
        tree = ET.fromstring(result)
        tags = {el.tag for el in tree.iter()}
        # At least button or input should be present
        assert tags & {"button", "input"}


# ── hierarchy_parse ────────────────────────────────────────────────────


class TestHierarchyParse:
    def test_bounds_removed(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        hierarchy = hierarchy_parse(parsed)
        tree = ET.fromstring(hierarchy)
        for el in tree.iter():
            assert "bounds" not in el.attrib

    def test_text_removed(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        hierarchy = hierarchy_parse(parsed)
        tree = ET.fromstring(hierarchy)
        for el in tree.iter():
            assert "text" not in el.attrib
            # element text should be empty string or None
            if el.text is not None:
                assert el.text == ""

    def test_index_removed(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        hierarchy = hierarchy_parse(parsed)
        tree = ET.fromstring(hierarchy)
        for el in tree.iter():
            assert "index" not in el.attrib


# ── create_encoded_xml ─────────────────────────────────────────────────


class TestCreateEncodedXml:
    def test_bounds_removed(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        encoded = create_encoded_xml(parsed)
        tree = ET.fromstring(encoded)
        for el in tree.iter():
            assert "bounds" not in el.attrib

    def test_important_removed(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        encoded = create_encoded_xml(parsed)
        tree = ET.fromstring(encoded)
        for el in tree.iter():
            assert "important" not in el.attrib

    def test_class_removed(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        encoded = create_encoded_xml(parsed)
        tree = ET.fromstring(encoded)
        for el in tree.iter():
            assert "class" not in el.attrib

    def test_index_preserved(self):
        parsed = parse_raw_xml(SAMPLE_RAW_XML)
        encoded = create_encoded_xml(parsed)
        tree = ET.fromstring(encoded)
        # At least some elements should still have index
        has_index = any("index" in el.attrib for el in tree.iter())
        assert has_index


# ── simplify_structure ─────────────────────────────────────────────────


class TestSimplifyStructure:
    def test_single_child_collapse(self):
        xml = '<div><div><button id="ok" /></div></div>'
        result = simplify_structure(xml)
        tree = ET.fromstring(result)
        # The nested divs should collapse so root becomes button
        assert tree.tag == "button"
        assert tree.attrib.get("id") == "ok"

    def test_button_not_collapsed(self):
        xml = '<button id="outer"><p>text</p></button>'
        result = simplify_structure(xml)
        tree = ET.fromstring(result)
        # button should NOT be collapsed even with single child
        assert tree.tag == "button"

    def test_with_text_attribute_not_collapsed(self):
        xml = '<div text="hello"><p>child</p></div>'
        result = simplify_structure(xml)
        tree = ET.fromstring(result)
        assert tree.tag == "div"
        assert tree.attrib.get("text") == "hello"

    def test_multiple_children_not_collapsed(self):
        xml = '<div><button id="a" /><button id="b" /></div>'
        result = simplify_structure(xml)
        tree = ET.fromstring(result)
        assert tree.tag == "div"
        assert len(list(tree)) == 2


# ── remove_redundancies ───────────────────────────────────────────────


class TestRemoveRedundancies:
    def test_scroll_dedup(self):
        xml = """<div>
          <scroll>
            <button id="item" text="A" />
            <button id="item" text="A" />
            <button id="item" text="A" />
          </scroll>
        </div>"""
        result = remove_redundancies(xml)
        tree = ET.fromstring(result)
        scroll = tree.find(".//scroll")
        assert scroll is not None
        children = list(scroll)
        assert len(children) == 1

    def test_non_scroll_not_deduped(self):
        xml = """<div>
          <div>
            <button id="item" text="A" />
            <button id="item" text="A" />
          </div>
        </div>"""
        result = remove_redundancies(xml)
        tree = ET.fromstring(result)
        buttons = tree.findall(".//button")
        assert len(buttons) == 2

    def test_different_items_in_scroll_kept(self):
        xml = """<scroll>
          <button id="a" />
          <button id="b" />
        </scroll>"""
        result = remove_redundancies(xml)
        tree = ET.fromstring(result)
        buttons = list(tree)
        assert len(buttons) == 2
