"""Tests for mobilegpt_collector.graphs.collector_graph."""

import pytest

from mobilegpt_collector.graphs.collector_graph import (
    build_collector_graph,
    compile_collector_graph,
)


class TestBuildCollectorGraph:
    def test_graph_builds_without_error(self):
        graph = build_collector_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        graph = build_collector_graph()
        node_names = set(graph.nodes.keys())
        assert "supervisor" in node_names
        assert "discover" in node_names
        assert "explore_action" in node_names


class TestCompileCollectorGraph:
    def test_compilation_succeeds(self):
        compiled = compile_collector_graph()
        assert compiled is not None
