"""Verification script for LabArchives MCP state management."""

import shutil
import tempfile
import unittest

from labarchives_mcp.state import StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.state_manager = StateManager(storage_dir=self.test_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)

    def test_create_and_switch_project(self) -> None:
        # Create with notebook IDs
        context = self.state_manager.create_project(
            "Test Proj", "Desc", linked_notebook_ids=["nb-1", "nb-2"]
        )
        self.assertEqual(context.name, "Test Proj")
        self.assertEqual(context.linked_notebook_ids, ["nb-1", "nb-2"])
        active = self.state_manager.get_active_context()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.id, context.id)

        # Create another
        context2 = self.state_manager.create_project("Proj 2", "Desc 2")
        active = self.state_manager.get_active_context()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.id, context2.id)

        # Switch back
        self.state_manager.switch_project(context.id)
        active = self.state_manager.get_active_context()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.id, context.id)

    def test_log_visit(self) -> None:
        self.state_manager.create_project("Proj 1", "Desc")
        self.state_manager.log_visit("nb1", "p1", "Page 1")

        context = self.state_manager.get_active_context()
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(len(context.visited_pages), 1)
        self.assertEqual(context.visited_pages[0].title, "Page 1")

    def test_log_finding(self) -> None:
        self.state_manager.create_project("Proj 1", "Desc")
        self.state_manager.log_finding("Eureka!")

        context = self.state_manager.get_active_context()
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(len(context.findings), 1)
        self.assertEqual(context.findings[0].content, "Eureka!")

    def test_delete_project(self) -> None:
        context = self.state_manager.create_project("To Delete", "Desc")
        proj_id = context.id

        # Verify it exists
        self.assertIn(proj_id, self.state_manager._state.contexts)

        # Delete it
        success = self.state_manager.delete_project(proj_id)
        self.assertTrue(success)
        self.assertNotIn(proj_id, self.state_manager._state.contexts)

        # Verify active context is cleared if we deleted the active one
        self.assertIsNone(self.state_manager.get_active_context())

    def test_graph_persistence(self) -> None:
        self.state_manager.create_project("Graph Proj", "Desc")
        self.state_manager.log_visit("nb1", "p1", "Page 1")
        self.state_manager.log_finding("Finding 1")

        context = self.state_manager.get_active_context()
        self.assertIsNotNone(context)
        assert context is not None
        graph_data = context.graph_data

        # Verify nodes and links exist in serialized data
        self.assertTrue(len(graph_data["nodes"]) >= 3)  # Project, Page, Finding
        self.assertTrue(len(graph_data["links"]) >= 2)  # Proj->Page, Proj->Finding

        # Verify we can deserialize it back to a graph (if networkx is installed)
        try:
            import networkx as nx

            graph = nx.node_link_graph(graph_data)
            self.assertTrue(graph.has_node(context.id))
            self.assertTrue(graph.has_edge(context.id, "page:p1"))
        except ImportError:
            pass  # Skip if networkx not installed in test env

    def test_graph_navigation_logic(self) -> None:
        """Simulate the logic used by get_related_pages and trace_provenance."""
        self.state_manager.create_project("Nav Proj", "Desc")

        # Log visits to two pages and a finding
        self.state_manager.log_visit("nb1", "p1", "Page 1")
        self.state_manager.log_visit("nb1", "p2", "Page 2")
        self.state_manager.log_finding("Finding A")

        context = self.state_manager.get_active_context()
        self.assertIsNotNone(context)
        assert context is not None
        graph_data = context.graph_data

        try:
            import networkx as nx
        except ImportError:
            return

        graph = nx.node_link_graph(graph_data)

        # Project node should connect to pages and findings
        neighbors = list(graph.neighbors(context.id))
        self.assertGreaterEqual(len(neighbors), 3)

        # Undirected view should show the sibling page relationship
        page_node = "page:p1"
        if graph.has_node(page_node):
            graph_undir = graph.to_undirected()
            siblings = {
                n.replace("page:", "")
                for n in graph_undir.neighbors(page_node)
                if graph.nodes[n].get("type") == "page"
            }
            self.assertIn("p2", siblings)


if __name__ == "__main__":
    unittest.main()
