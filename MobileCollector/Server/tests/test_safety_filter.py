"""Tests for mobilecollector.agents.safety_filter."""

import pytest

from mobilecollector.data.models import Subtask
from mobilecollector.agents.safety_filter import SafetyFilter


class TestSafetyFilter:
    def test_purchase_is_unsafe(self):
        sf = SafetyFilter(enabled=True)
        subtasks = [Subtask(name="purchase_item", description="Buy an item")]
        safe, unsafe = sf.filter(subtasks)
        assert len(safe) == 0
        assert len(unsafe) == 1
        assert unsafe[0].name == "purchase_item"

    def test_view_settings_is_safe(self):
        sf = SafetyFilter(enabled=True)
        subtasks = [Subtask(name="view_settings", description="Open settings page")]
        safe, unsafe = sf.filter(subtasks)
        assert len(safe) == 1
        assert len(unsafe) == 0
        assert safe[0].name == "view_settings"

    def test_empty_list(self):
        sf = SafetyFilter(enabled=True)
        safe, unsafe = sf.filter([])
        assert safe == []
        assert unsafe == []

    def test_mixed_safe_and_unsafe(self):
        sf = SafetyFilter(enabled=True)
        subtasks = [
            Subtask(name="view_settings", description="Open settings"),
            Subtask(name="purchase_item", description="Buy something"),
            Subtask(name="scroll_list", description="Scroll through list"),
            Subtask(name="delete_account", description="Remove account"),
            Subtask(name="view_profile", description="View user profile"),
        ]
        safe, unsafe = sf.filter(subtasks)

        safe_names = [s.name for s in safe]
        unsafe_names = [s.name for s in unsafe]

        assert "view_settings" in safe_names
        assert "scroll_list" in safe_names
        assert "view_profile" in safe_names

        assert "purchase_item" in unsafe_names
        assert "delete_account" in unsafe_names

    def test_disabled_filter_passes_all(self):
        sf = SafetyFilter(enabled=False)
        subtasks = [
            Subtask(name="purchase_item", description="Buy something"),
            Subtask(name="delete_all", description="Delete everything"),
        ]
        safe, unsafe = sf.filter(subtasks)
        assert len(safe) == 2
        assert len(unsafe) == 0

    def test_unsafe_in_description_only(self):
        sf = SafetyFilter(enabled=True)
        subtasks = [
            Subtask(name="confirm_action", description="purchase confirmation dialog"),
        ]
        safe, unsafe = sf.filter(subtasks)
        assert len(unsafe) == 1

    def test_case_insensitive(self):
        sf = SafetyFilter(enabled=True)
        subtasks = [
            Subtask(name="PURCHASE_ITEM", description=""),
        ]
        safe, unsafe = sf.filter(subtasks)
        assert len(unsafe) == 1

    def test_financial_keywords(self):
        sf = SafetyFilter(enabled=True)
        for keyword in ["pay", "subscribe", "order", "buy", "checkout", "transaction"]:
            subtasks = [Subtask(name=f"do_{keyword}", description="")]
            safe, unsafe = sf.filter(subtasks)
            assert len(unsafe) == 1, f"'{keyword}' should be filtered as unsafe"

    def test_system_keywords(self):
        sf = SafetyFilter(enabled=True)
        for keyword in ["install", "uninstall", "reset", "factory_reset"]:
            subtasks = [Subtask(name=f"do_{keyword}", description="")]
            safe, unsafe = sf.filter(subtasks)
            assert len(unsafe) == 1, f"'{keyword}' should be filtered as unsafe"

    def test_communication_keywords(self):
        sf = SafetyFilter(enabled=True)
        for keyword in ["send", "post", "message", "call", "email"]:
            subtasks = [Subtask(name=f"do_{keyword}", description="")]
            safe, unsafe = sf.filter(subtasks)
            assert len(unsafe) == 1, f"'{keyword}' should be filtered as unsafe"
