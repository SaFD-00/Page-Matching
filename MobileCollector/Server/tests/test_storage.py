"""Tests for mobilecollector.storage and mobilecollector.memory modules."""

import json
import os

import pytest

from mobilecollector.data.models import (
    Subtask,
    UIAttributes,
    ExplorationState,
    PageKnowledge,
)
from mobilecollector.storage.page_storage import PageStorage
from mobilecollector.memory.state_persistence import StatePersistence
from mobilecollector.matching.page_registry import PageRegistry
from mobilecollector.memory.collector_memory import CollectorMemory


# ── Helpers ────────────────────────────────────────────────────────────


def _make_ui_attrs(tag: str = "button", elem_id: str = "btn") -> UIAttributes:
    return UIAttributes(
        **{
            "self": {"tag": tag, "id": elem_id, "class": "NONE"},
            "parent": {},
            "children": [],
        }
    )


# ── PageStorage ────────────────────────────────────────────────────────


class TestPageStorage:
    def test_save_page_creates_all_files(self, tmp_path):
        storage = PageStorage(str(tmp_path))
        subtasks = [Subtask(name="search", description="do search")]
        keyuis = {"search": [_make_ui_attrs("button", "search_btn")]}

        page_dir = storage.save_page(
            app_name="TestApp",
            bundle_num=0,
            page_num=0,
            raw_xml="<raw/>",
            parsed_xml="<parsed/>",
            hierarchy_xml="<hierarchy/>",
            encoded_xml="<encoded/>",
            pretty_xml="<pretty/>",
            screenshot_path="",
            subtasks=subtasks,
            keyuis=keyuis,
        )

        expected_files = [
            "0.xml",               # raw
            "0_parsed.xml",        # parsed
            "0_hierarchy_parsed.xml",  # hierarchy
            "0_encoded.xml",       # encoded
            "0_pretty.xml",        # pretty
            "subtask.json",
            "keyui.json",
        ]
        for fname in expected_files:
            fpath = os.path.join(page_dir, fname)
            assert os.path.exists(fpath), f"Missing file: {fname}"

    def test_save_page_xml_contents(self, tmp_path):
        storage = PageStorage(str(tmp_path))
        storage.save_page(
            app_name="App",
            bundle_num=1,
            page_num=2,
            raw_xml="<raw>data</raw>",
            parsed_xml="<parsed>data</parsed>",
            hierarchy_xml="<hierarchy>data</hierarchy>",
            encoded_xml="<encoded>data</encoded>",
            pretty_xml="<pretty>data</pretty>",
            screenshot_path="",
            subtasks=[],
            keyuis={},
        )
        page_dir = os.path.join(str(tmp_path), "App", "1", "2")
        with open(os.path.join(page_dir, "2.xml"), "r") as f:
            assert f.read() == "<raw>data</raw>"

    def test_save_page_subtask_json_content(self, tmp_path):
        storage = PageStorage(str(tmp_path))
        subtasks = [
            Subtask(name="search", description="do search", parameters={"q": "str"})
        ]
        page_dir = storage.save_page(
            app_name="App",
            bundle_num=0,
            page_num=0,
            raw_xml="<r/>",
            parsed_xml="<p/>",
            hierarchy_xml="<h/>",
            encoded_xml="<e/>",
            pretty_xml="<pr/>",
            screenshot_path="",
            subtasks=subtasks,
            keyuis={},
        )
        with open(os.path.join(page_dir, "subtask.json"), "r") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["name"] == "search"
        assert data[0]["parameters"] == {"q": "str"}

    def test_save_page_keyui_json_content(self, tmp_path):
        storage = PageStorage(str(tmp_path))
        keyuis = {"task1": [_make_ui_attrs("button", "btn1")]}
        page_dir = storage.save_page(
            app_name="App",
            bundle_num=0,
            page_num=0,
            raw_xml="<r/>",
            parsed_xml="<p/>",
            hierarchy_xml="<h/>",
            encoded_xml="<e/>",
            pretty_xml="<pr/>",
            screenshot_path="",
            subtasks=[],
            keyuis=keyuis,
        )
        with open(os.path.join(page_dir, "keyui.json"), "r") as f:
            data = json.load(f)
        assert "task1" in data
        assert data["task1"][0]["self"]["tag"] == "button"

    def test_save_page_directory_structure(self, tmp_path):
        storage = PageStorage(str(tmp_path))
        storage.save_page(
            app_name="MyApp",
            bundle_num=2,
            page_num=3,
            raw_xml="<r/>",
            parsed_xml="<p/>",
            hierarchy_xml="<h/>",
            encoded_xml="<e/>",
            pretty_xml="<pr/>",
            screenshot_path="",
            subtasks=[],
            keyuis={},
        )
        page_dir = os.path.join(str(tmp_path), "MyApp", "2", "3")
        assert os.path.isdir(page_dir)


# ── StatePersistence ───────────────────────────────────────────────────


class TestStatePersistence:
    def test_save_and_load_state_round_trip(self, tmp_path):
        sp = StatePersistence(str(tmp_path), "TestApp")
        state = ExplorationState(
            app_name="TestApp",
            visited_pages=[0, 1, 2],
            bundle_count=2,
            total_pages_collected=3,
            page_counter=3,
        )
        sp.save_state(state)

        loaded = sp.load_state()
        assert loaded is not None
        assert loaded.app_name == "TestApp"
        assert loaded.visited_pages == [0, 1, 2]
        assert loaded.bundle_count == 2
        assert loaded.total_pages_collected == 3
        assert loaded.last_updated != ""  # should have been set

    def test_load_state_no_file(self, tmp_path):
        sp = StatePersistence(str(tmp_path), "TestApp")
        assert sp.load_state() is None

    def test_has_saved_state(self, tmp_path):
        sp = StatePersistence(str(tmp_path), "TestApp")
        assert sp.has_saved_state() is False
        sp.save_state(ExplorationState(app_name="TestApp"))
        assert sp.has_saved_state() is True

    def test_save_and_load_registry_round_trip(self, tmp_path):
        sp = StatePersistence(str(tmp_path), "TestApp")
        reg = PageRegistry()
        reg.add(PageKnowledge(
            bundle_id="0",
            app_name="TestApp",
            subtasks=[Subtask(name="search")],
            keyuis={"search": [_make_ui_attrs()]},
        ))
        sp.save_registry(reg)

        loaded_reg = sp.load_registry()
        assert loaded_reg is not None
        assert len(loaded_reg) == 1
        assert loaded_reg.get("0").app_name == "TestApp"
        assert loaded_reg.get("0").subtasks[0].name == "search"

    def test_load_registry_no_file(self, tmp_path):
        sp = StatePersistence(str(tmp_path), "TestApp")
        assert sp.load_registry() is None


# ── CollectorMemory ────────────────────────────────────────────────────


class TestCollectorMemory:
    def test_initialize_new(self, tmp_path):
        mem = CollectorMemory(str(tmp_path), "TestApp", threshold=1.0)
        result = mem.initialize()
        # No existing state, should return None
        assert result is None
        assert mem.get_page_counter() == 0

    def test_initialize_with_existing_state(self, tmp_path):
        # First, save state manually
        sp = StatePersistence(str(tmp_path), "TestApp")
        state = ExplorationState(
            app_name="TestApp",
            visited_pages=[0, 1],
            page_counter=2,
            bundle_count=1,
        )
        sp.save_state(state)

        reg = PageRegistry()
        reg.add(PageKnowledge(bundle_id="0", app_name="TestApp"))
        sp.save_registry(reg)

        # Now initialize CollectorMemory
        mem = CollectorMemory(str(tmp_path), "TestApp", threshold=1.0)
        loaded_state = mem.initialize()
        assert loaded_state is not None
        assert loaded_state.page_counter == 2
        assert mem.get_page_counter() == 2
