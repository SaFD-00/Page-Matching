"""Tests for mobilegpt_collector.data.models."""

import pytest

from mobilegpt_collector.data.models import (
    UIAttributes,
    Subtask,
    PageKnowledge,
    MatchResult,
    BundleInfo,
    ExplorationState,
)


# ── UIAttributes ───────────────────────────────────────────────────────


class TestUIAttributes:
    def test_creation_defaults(self):
        ui = UIAttributes()
        assert ui.self_attrs == {}
        assert ui.parent == {}
        assert ui.children == []

    def test_creation_with_values(self):
        ui = UIAttributes(
            **{
                "self": {"tag": "button", "id": "ok_btn"},
                "parent": {"tag": "div", "id": "container"},
                "children": [({"tag": "p", "id": "NONE"}, 1, 0)],
            }
        )
        assert ui.self_attrs == {"tag": "button", "id": "ok_btn"}
        assert ui.parent == {"tag": "div", "id": "container"}
        assert len(ui.children) == 1

    def test_to_dict(self):
        ui = UIAttributes(
            **{
                "self": {"tag": "button"},
                "parent": {"tag": "div"},
                "children": [],
            }
        )
        d = ui.to_dict()
        assert d["self"] == {"tag": "button"}
        assert d["parent"] == {"tag": "div"}
        assert d["children"] == []

    def test_to_dict_round_trip(self):
        original = {
            "self": {"tag": "input", "id": "search"},
            "parent": {"tag": "div"},
            "children": [({"tag": "img"}, 1, 0)],
        }
        ui = UIAttributes(**original)
        d = ui.to_dict()
        ui2 = UIAttributes(**d)
        assert ui2.to_dict() == d


# ── Subtask ────────────────────────────────────────────────────────────


class TestSubtask:
    def test_creation_minimal(self):
        s = Subtask(name="view_settings")
        assert s.name == "view_settings"
        assert s.description == ""
        assert s.parameters == {}

    def test_creation_full(self):
        s = Subtask(
            name="search",
            description="Search for items",
            parameters={"query": "string"},
        )
        assert s.name == "search"
        assert s.description == "Search for items"
        assert s.parameters == {"query": "string"}

    def test_extra_fields_ignored(self):
        s = Subtask(name="test", extra_field="ignored")
        assert s.name == "test"
        assert not hasattr(s, "extra_field")


# ── PageKnowledge ──────────────────────────────────────────────────────


class TestPageKnowledge:
    def test_subtask_names_empty(self):
        pk = PageKnowledge(bundle_id="0", app_name="test")
        assert [s.name for s in pk.subtasks] == []

    def test_subtask_names(self):
        pk = PageKnowledge(
            bundle_id="0",
            app_name="test",
            subtasks=[
                Subtask(name="search"),
                Subtask(name="settings"),
                Subtask(name="profile"),
            ],
        )
        assert [s.name for s in pk.subtasks] == ["search", "settings", "profile"]


# ── MatchResult ────────────────────────────────────────────────────────


class TestMatchResult:
    def test_is_match_eqset(self):
        r = MatchResult(
            query_page_id="0",
            candidate_bundle_id="1",
            match_type="EQSET",
            supported_subtasks=["search"],
            match_ratio=1.0,
            threshold=1.0,
        )
        assert r.is_match() is True

    def test_is_match_superset(self):
        r = MatchResult(
            query_page_id="0",
            candidate_bundle_id="1",
            match_type="SUPERSET",
            supported_subtasks=["a", "b"],
            match_ratio=1.0,
            threshold=1.0,
        )
        assert r.is_match() is True

    def test_is_match_subset(self):
        r = MatchResult(
            query_page_id="0",
            candidate_bundle_id="1",
            match_type="SUBSET",
            supported_subtasks=["a"],
            match_ratio=0.5,
            threshold=0.5,
        )
        assert r.is_match() is True

    def test_is_match_new_always_false(self):
        r = MatchResult(
            query_page_id="0",
            candidate_bundle_id="1",
            match_type="NEW",
            supported_subtasks=["a"],
            match_ratio=1.0,
            threshold=1.0,
        )
        assert r.is_match() is False

    def test_is_match_below_threshold(self):
        r = MatchResult(
            query_page_id="0",
            candidate_bundle_id="1",
            match_type="SUPERSET",
            supported_subtasks=["a"],
            match_ratio=0.3,
            threshold=0.5,
        )
        assert r.is_match() is False

    def test_is_match_no_supported(self):
        r = MatchResult(
            query_page_id="0",
            candidate_bundle_id="1",
            match_type="EQSET",
            supported_subtasks=[],
            match_ratio=0.0,
            threshold=1.0,
        )
        assert r.is_match() is False


# ── BundleInfo ─────────────────────────────────────────────────────────


class TestBundleInfo:
    def test_instantiation(self):
        b = BundleInfo(bundle_id="0", bundle_num=0, app_name="TestApp")
        assert b.bundle_id == "0"
        assert b.bundle_num == 0
        assert b.app_name == "TestApp"
        assert b.pages == []
        assert b.representative_page == 0
        assert b.subtasks == []
        assert b.keyuis == {}


# ── ExplorationState ───────────────────────────────────────────────────


class TestExplorationState:
    def test_instantiation_defaults(self):
        es = ExplorationState(app_name="TestApp")
        assert es.app_name == "TestApp"
        assert es.threshold == 1.0
        assert es.visited_pages == []
        assert es.bundle_count == 0
        assert es.total_pages_collected == 0
        assert es.page_counter == 0

    def test_instantiation_with_values(self):
        es = ExplorationState(
            app_name="TestApp",
            visited_pages=[0, 1, 2],
            bundle_count=2,
            total_pages_collected=3,
            page_counter=3,
        )
        assert es.visited_pages == [0, 1, 2]
        assert es.bundle_count == 2
        assert es.total_pages_collected == 3
