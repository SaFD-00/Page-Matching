"""Tests for mobilecollector.matching modules."""

import json
import os

import pytest

from mobilecollector.data.models import (
    UIAttributes,
    Subtask,
    PageKnowledge,
    MatchResult,
)
from mobilecollector.matching.ui_matcher import UIMatcher
from mobilecollector.matching.page_registry import PageRegistry
from mobilecollector.matching.page_matcher import PageMatcher
from mobilecollector.matching.bundle_manager import BundleManager


# ── Fixtures & helpers ─────────────────────────────────────────────────

# A minimal parsed XML with index/bounds for matching tests
PARSED_XML = (
    '<div index="0" bounds="[0,0][1080,2400]">'
    '<button index="1" id="search_btn" bounds="[0,100][540,200]" />'
    '<input index="2" id="input_field" description="Enter text" bounds="[0,200][1080,300]" />'
    '<img index="3" description="Logo" bounds="[100,300][200,400]" />'
    '<checker index="4" id="chk" bounds="[0,400][100,500]" />'
    "</div>"
)


def _make_ui_attrs(tag: str, elem_id: str = "NONE", desc: str = "NONE") -> UIAttributes:
    return UIAttributes(
        **{
            "self": {"tag": tag, "id": elem_id, "class": "NONE", "description": desc},
            "parent": {},
            "children": [],
        }
    )


# ── UIMatcher ──────────────────────────────────────────────────────────


class TestUIMatcher:
    def test_match_keyuis_all_found(self):
        matcher = UIMatcher(PARSED_XML)
        keyuis = {
            "search": [_make_ui_attrs("button", "search_btn")],
            "type_text": [_make_ui_attrs("input", "input_field")],
        }
        supported, unsupported, matched_indexes = matcher.match_keyuis(keyuis)
        assert "search" in supported
        assert "type_text" in supported
        assert unsupported == []
        assert 1 in matched_indexes
        assert 2 in matched_indexes

    def test_match_keyuis_none_found(self):
        matcher = UIMatcher(PARSED_XML)
        keyuis = {
            "nonexistent": [_make_ui_attrs("button", "no_such_id")],
        }
        supported, unsupported, matched_indexes = matcher.match_keyuis(keyuis)
        assert supported == []
        assert "nonexistent" in unsupported
        assert len(matched_indexes) == 0

    def test_match_keyuis_partial(self):
        matcher = UIMatcher(PARSED_XML)
        keyuis = {
            "search": [_make_ui_attrs("button", "search_btn")],
            "missing": [_make_ui_attrs("button", "nope")],
        }
        supported, unsupported, _ = matcher.match_keyuis(keyuis)
        assert "search" in supported
        assert "missing" in unsupported

    def test_get_all_interactable_indexes(self):
        matcher = UIMatcher(PARSED_XML)
        indexes = matcher.get_all_interactable_indexes()
        # button(1), input(2), checker(4) should all be interactable
        assert 1 in indexes
        assert 2 in indexes
        assert 4 in indexes
        # img(3) is not interactable
        assert 3 not in indexes

    def test_get_remaining_indexes(self):
        matcher = UIMatcher(PARSED_XML)
        matched = {1, 2}
        remaining = matcher.get_remaining_indexes(matched)
        assert 1 not in remaining
        assert 2 not in remaining
        assert 4 in remaining

    def test_has_match_true(self):
        matcher = UIMatcher(PARSED_XML)
        assert matcher.has_match(_make_ui_attrs("button", "search_btn")) is True

    def test_has_match_false(self):
        matcher = UIMatcher(PARSED_XML)
        assert matcher.has_match(_make_ui_attrs("button", "no_exist")) is False


# ── PageRegistry ───────────────────────────────────────────────────────


class TestPageRegistry:
    def test_add_and_get(self):
        reg = PageRegistry()
        pk = PageKnowledge(bundle_id="0", app_name="test")
        reg.add(pk)
        assert reg.get("0") is not None
        assert reg.get("0").app_name == "test"

    def test_get_nonexistent(self):
        reg = PageRegistry()
        assert reg.get("99") is None

    def test_get_all_bundle_ids(self):
        reg = PageRegistry()
        reg.add(PageKnowledge(bundle_id="0", app_name="a"))
        reg.add(PageKnowledge(bundle_id="1", app_name="b"))
        ids = reg.get_all_bundle_ids()
        assert set(ids) == {"0", "1"}

    def test_len_and_contains(self):
        reg = PageRegistry()
        reg.add(PageKnowledge(bundle_id="0", app_name="a"))
        assert len(reg) == 1
        assert "0" in reg
        assert "1" not in reg

    def test_remove(self):
        reg = PageRegistry()
        reg.add(PageKnowledge(bundle_id="0", app_name="a"))
        reg.remove("0")
        assert "0" not in reg
        assert len(reg) == 0

    def test_to_dict_from_dict_round_trip(self):
        reg = PageRegistry()
        pk = PageKnowledge(
            bundle_id="0",
            app_name="test",
            subtasks=[Subtask(name="search", description="do search")],
            keyuis={
                "search": [_make_ui_attrs("button", "search_btn")]
            },
        )
        reg.add(pk)

        data = reg.to_dict()
        reg2 = PageRegistry.from_dict(data)

        assert reg2.get("0") is not None
        assert reg2.get("0").app_name == "test"
        assert len(reg2.get("0").subtasks) == 1
        assert reg2.get("0").subtasks[0].name == "search"
        assert "search" in reg2.get("0").keyuis

    def test_add_subtask(self):
        reg = PageRegistry()
        pk = PageKnowledge(bundle_id="0", app_name="test")
        reg.add(pk)
        reg.add_subtask("0", Subtask(name="new_task"))
        assert "new_task" in reg.get("0").get_all_subtask_names()

    def test_add_subtask_no_duplicate(self):
        reg = PageRegistry()
        pk = PageKnowledge(
            bundle_id="0",
            app_name="test",
            subtasks=[Subtask(name="task")],
        )
        reg.add(pk)
        reg.add_subtask("0", Subtask(name="task"))
        assert len(reg.get("0").subtasks) == 1


# ── PageMatcher ────────────────────────────────────────────────────────


class TestPageMatcher:
    def _setup_registry_with_bundle(self):
        """Set up a registry with one known bundle matching PARSED_XML."""
        reg = PageRegistry()
        pk = PageKnowledge(
            bundle_id="0",
            app_name="test",
            subtasks=[
                Subtask(name="search"),
                Subtask(name="type_text"),
                Subtask(name="toggle"),
            ],
            keyuis={
                "search": [_make_ui_attrs("button", "search_btn")],
                "type_text": [_make_ui_attrs("input", "input_field")],
                "toggle": [_make_ui_attrs("checker", "chk")],
            },
        )
        reg.add(pk)
        return reg

    def test_match_eqset(self):
        """All subtasks matched, no remaining interactable UIs."""
        reg = self._setup_registry_with_bundle()
        matcher = PageMatcher(reg, threshold=1.0)
        result = matcher.match(PARSED_XML, "0", query_page_id="q1")
        assert result.match_type == "EQSET"
        assert result.is_match() is True

    def test_match_subset(self):
        """Only some subtasks matched, but no remaining UIs (partial knowledge)."""
        reg = PageRegistry()
        pk = PageKnowledge(
            bundle_id="0",
            app_name="test",
            subtasks=[
                Subtask(name="search"),
                Subtask(name="type_text"),
                Subtask(name="toggle"),
                Subtask(name="ghost"),  # extra subtask with no UI
            ],
            keyuis={
                "search": [_make_ui_attrs("button", "search_btn")],
                "type_text": [_make_ui_attrs("input", "input_field")],
                "toggle": [_make_ui_attrs("checker", "chk")],
                "ghost": [_make_ui_attrs("button", "no_exist")],
            },
        )
        reg.add(pk)
        matcher = PageMatcher(reg, threshold=1.0)
        result = matcher.match(PARSED_XML, "0", query_page_id="q1")
        # 3 out of 4 matched, ratio=0.75 < threshold 1.0; remaining=0 but ratio < threshold
        # With remaining=0 and match_ratio > 0 but < 1.0 => SUBSET
        assert result.match_type == "SUBSET"

    def test_match_superset(self):
        """All known subtasks matched but there are extra UIs on the page."""
        reg = PageRegistry()
        pk = PageKnowledge(
            bundle_id="0",
            app_name="test",
            subtasks=[Subtask(name="search")],
            keyuis={"search": [_make_ui_attrs("button", "search_btn")]},
        )
        reg.add(pk)
        matcher = PageMatcher(reg, threshold=1.0)
        result = matcher.match(PARSED_XML, "0", query_page_id="q1")
        # 1/1 matched (ratio=1.0 >= threshold), but remaining > 0 => SUPERSET
        assert result.match_type == "SUPERSET"
        assert len(result.remaining_ui_indexes) > 0

    def test_match_new_no_bundle(self):
        """No matching bundle in registry."""
        reg = PageRegistry()
        matcher = PageMatcher(reg, threshold=1.0)
        result = matcher.match(PARSED_XML, "nonexistent", query_page_id="q1")
        assert result.match_type == "NEW"
        assert result.is_match() is False

    def test_find_best_match_returns_best(self):
        reg = self._setup_registry_with_bundle()
        matcher = PageMatcher(reg, threshold=1.0)
        best = matcher.find_best_match(PARSED_XML, "q1")
        assert best is not None
        assert best.match_type == "EQSET"

    def test_find_best_match_none_when_empty(self):
        reg = PageRegistry()
        matcher = PageMatcher(reg, threshold=1.0)
        best = matcher.find_best_match(PARSED_XML, "q1")
        assert best is None


# ── BundleManager ──────────────────────────────────────────────────────


class TestBundleManager:
    def test_create_bundle(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        subtasks = [Subtask(name="search")]
        keyuis = {"search": [_make_ui_attrs("button", "search_btn")]}
        bundle_num = bm.create_bundle(subtasks, keyuis)
        assert bundle_num == 0
        assert bm.bundle_count == 1
        # Check directory was created
        assert os.path.isdir(os.path.join(str(tmp_path), "TestApp", "0"))
        # Check registry was updated
        assert reg.get("0") is not None

    def test_add_page_to_bundle(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        bm.create_bundle([Subtask(name="s1")], {})
        page_num = bm.add_page_to_bundle(0, page_index=10)
        assert page_num == 0
        assert bm.total_pages == 1
        assert bm.get_bundle_for_page(10) == 0
        # Page directory should be created
        assert os.path.isdir(os.path.join(str(tmp_path), "TestApp", "0", "0"))

    def test_add_page_to_nonexistent_bundle(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        page_num = bm.add_page_to_bundle(99, page_index=1)
        assert page_num == 0  # returns 0 when bundle not found

    def test_expand_bundle(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        bm.create_bundle([Subtask(name="search")], {"search": []})
        bm.expand_bundle(
            0,
            [Subtask(name="settings"), Subtask(name="search")],  # duplicate should be ignored
            {"settings": [_make_ui_attrs("button", "settings_btn")]},
        )
        info = bm.get_bundle_info(0)
        subtask_names = [s.name for s in info.subtasks]
        assert "search" in subtask_names
        assert "settings" in subtask_names
        assert len(subtask_names) == 2  # no duplicate

    def test_save_load_bundle_map_round_trip(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        bm.create_bundle(
            [Subtask(name="search", description="d")],
            {"search": [_make_ui_attrs("button", "b")]},
        )
        bm.add_page_to_bundle(0, page_index=5)
        bm.save_bundle_map()

        # Load into a new manager
        reg2 = PageRegistry()
        bm2 = BundleManager(str(tmp_path), "TestApp", reg2)
        loaded = bm2.load_bundle_map()
        assert loaded is True
        assert bm2.bundle_count == 1
        info = bm2.get_bundle_info(0)
        assert info is not None
        assert info.pages == [5]
        assert info.subtasks[0].name == "search"

    def test_load_bundle_map_no_file(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        assert bm.load_bundle_map() is False

    def test_multiple_bundles(self, tmp_path):
        reg = PageRegistry()
        bm = BundleManager(str(tmp_path), "TestApp", reg)
        b0 = bm.create_bundle([Subtask(name="a")], {})
        b1 = bm.create_bundle([Subtask(name="b")], {})
        assert b0 == 0
        assert b1 == 1
        assert bm.bundle_count == 2
