"""Tests for mobilegpt_collector.agents.safety_filter."""

import pytest

from mobilegpt_collector.data.models import Subtask
from mobilegpt_collector.agents.safety_filter import SafetyFilter


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
        for keyword in ["pay", "subscribe", "buy", "checkout", "transaction"]:
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
        for keyword in ["send", "compose", "post", "dial"]:
            subtasks = [Subtask(name=f"do_{keyword}", description="")]
            safe, unsafe = sf.filter(subtasks)
            assert len(unsafe) == 1, f"'{keyword}' should be filtered as unsafe"

    def test_token_matching_no_false_positives(self):
        """Verify token-based matching doesn't produce false positives."""
        sf = SafetyFilter(enabled=True)
        # These should be SAFE (partial substring match would wrongly block them)
        safe_subtasks = [
            Subtask(name="browse_message_list", description="Browse messages"),
            Subtask(name="open_message_thread", description="Open a thread"),
            Subtask(name="search_messages", description="Search messages"),
            Subtask(name="view_email_inbox", description="View inbox"),
            Subtask(name="reorder_items", description="Reorder the list"),
            Subtask(name="display_payment_history", description="Show history"),
        ]
        for subtask in safe_subtasks:
            safe, unsafe = sf.filter([subtask])
            assert len(safe) == 1, f"'{subtask.name}' should be safe but was filtered"

    def test_compose_message_is_unsafe(self):
        """Verify compose (write action) is correctly blocked."""
        sf = SafetyFilter(enabled=True)
        subtasks = [Subtask(name="compose_new_message", description="Write a new message")]
        safe, unsafe = sf.filter(subtasks)
        assert len(unsafe) == 1
