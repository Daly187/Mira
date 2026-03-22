"""
Knowledge graph — NetworkX + SQLite for connected relationships.
People → events → decisions → ideas — everything linked.

Answers questions like:
- 'Who have I spoken to about the Boldr Philippines restructure?'
- 'What ideas came out of my last trip to South Africa?'
- 'Show me all the times I changed my mind about a trading strategy'
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import networkx as nx

logger = logging.getLogger("mira.memory.graph")


class KnowledgeGraph:
    """Connected graph of people, events, ideas, decisions, and their relationships."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.graph = nx.DiGraph()
        self.conn = None

    def initialise(self):
        """Load or create the knowledge graph."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._load_graph()
        logger.info(
            f"Knowledge graph initialised: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    def _create_tables(self):
        """Create persistence tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relationship TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source) REFERENCES nodes(id),
                FOREIGN KEY (target) REFERENCES nodes(id),
                UNIQUE(source, target, relationship)
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
            CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relationship);
        """)
        self.conn.commit()

    def _load_graph(self):
        """Load graph from SQLite into NetworkX."""
        self.graph.clear()

        nodes = self.conn.execute("SELECT * FROM nodes").fetchall()
        for node in nodes:
            self.graph.add_node(
                node["id"],
                node_type=node["node_type"],
                label=node["label"],
                properties=json.loads(node["properties"]),
                created_at=node["created_at"],
            )

        edges = self.conn.execute("SELECT * FROM edges").fetchall()
        for edge in edges:
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                relationship=edge["relationship"],
                properties=json.loads(edge["properties"]),
                created_at=edge["created_at"],
            )

    # ── Node Operations ──────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        properties: dict = None,
    ):
        """Add a node (person, event, idea, decision, topic, etc.)."""
        props = json.dumps(properties or {})
        self.conn.execute(
            """INSERT INTO nodes (id, node_type, label, properties)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET label = ?, properties = ?""",
            (node_id, node_type, label, props, label, props),
        )
        self.conn.commit()
        self.graph.add_node(
            node_id,
            node_type=node_type,
            label=label,
            properties=properties or {},
            created_at=datetime.now().isoformat(),
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: dict = None,
    ):
        """Connect two nodes with a relationship."""
        props = json.dumps(properties or {})
        try:
            self.conn.execute(
                """INSERT INTO edges (source, target, relationship, properties)
                   VALUES (?, ?, ?, ?)""",
                (source_id, target_id, relationship, props),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # Edge already exists

        self.graph.add_edge(
            source_id,
            target_id,
            relationship=relationship,
            properties=properties or {},
        )

    # ── Query Operations ─────────────────────────────────────────────

    def get_connections(self, node_id: str, depth: int = 1) -> dict:
        """Get all nodes connected to a given node, up to N hops."""
        if node_id not in self.graph:
            return {"node": None, "connections": []}

        node_data = self.graph.nodes[node_id]
        connections = []

        # BFS up to depth
        visited = {node_id}
        queue = [(node_id, 0)]

        while queue:
            current, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue

            # Outgoing edges
            for _, target, data in self.graph.out_edges(current, data=True):
                if target not in visited:
                    visited.add(target)
                    target_data = self.graph.nodes[target]
                    connections.append({
                        "id": target,
                        "label": target_data.get("label", ""),
                        "type": target_data.get("node_type", ""),
                        "relationship": data.get("relationship", ""),
                        "direction": "outgoing",
                        "hops": current_depth + 1,
                    })
                    queue.append((target, current_depth + 1))

            # Incoming edges
            for source, _, data in self.graph.in_edges(current, data=True):
                if source not in visited:
                    visited.add(source)
                    source_data = self.graph.nodes[source]
                    connections.append({
                        "id": source,
                        "label": source_data.get("label", ""),
                        "type": source_data.get("node_type", ""),
                        "relationship": data.get("relationship", ""),
                        "direction": "incoming",
                        "hops": current_depth + 1,
                    })
                    queue.append((source, current_depth + 1))

        return {
            "node": {"id": node_id, **node_data},
            "connections": connections,
        }

    def find_nodes(self, node_type: str = None, label_contains: str = None) -> list[dict]:
        """Find nodes by type and/or label."""
        results = []
        for node_id, data in self.graph.nodes(data=True):
            if node_type and data.get("node_type") != node_type:
                continue
            if label_contains and label_contains.lower() not in data.get("label", "").lower():
                continue
            results.append({"id": node_id, **data})
        return results

    def find_path(self, source_id: str, target_id: str) -> list:
        """Find the shortest path between two nodes."""
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            result = []
            for i, node_id in enumerate(path):
                node_data = self.graph.nodes[node_id]
                entry = {"id": node_id, **node_data}
                if i < len(path) - 1:
                    edge_data = self.graph.edges[node_id, path[i + 1]]
                    entry["edge_to_next"] = edge_data.get("relationship", "")
                result.append(entry)
            return result
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_stats(self) -> dict:
        """Graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": dict(
                self.conn.execute(
                    "SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type"
                ).fetchall()
            ),
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
