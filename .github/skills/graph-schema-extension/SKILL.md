---
name: graph-schema-extension
description: 'Workflow for extending Neo4j graph schema in AICA. Use when: adding new node types, creating relationships, modifying graph structure, integrating new scanner data, building graph queries.'
argument-hint: 'Describe what to add (e.g., "add middleware nodes", "create component relationships")'
---

# Graph Schema Extension Workflow

Complete workflow for extending AICA's Neo4j graph schema with new node types and relationships.

## When to Use

- Adding new node types to the knowledge graph
- Creating new relationship types between existing nodes
- Integrating new scanner detector output into the graph
- Modifying existing graph structure
- Building Cypher queries for graph analysis

## Prerequisites

- Neo4j database running (local or remote)
- Understanding of Neo4j graph concepts (nodes, relationships, properties)
- Scanner detector output available (if integrating new data)
- Familiarity with Cypher query language basics

## Architecture Overview

AICA's graph store uses a builder pattern:

```
Scanner Output → Graph Builders → Neo4j Client → Neo4j Database
```

**Key components:**

- `schema.py` - Node and relationship type definitions
- `node_builder.py` - Creates node dictionaries
- `*_builder.py` - Specialized builders (imports, calls, scanner)
- `neo4j_client.py` - Database operations
- `graph_builder.py` - Orchestrates the build process

## Workflow Steps

### 1. Define Schema Types

**Location:** `aica/memory/graph_store/schema.py`

**Add node type enum:**

```python
class NodeType(str, Enum):
    """Node types in the repository graph."""

    # Existing types
    FILE = "File"
    FUNCTION = "Function"
    CLASS = "Class"

    # Add your new type
    MIDDLEWARE = "Middleware"  # Example
    API_ROUTE = "ApiRoute"     # Example
```

**Add relationship type enum:**

```python
class RelType(str, Enum):
    """Relationship types in the repository graph."""

    # Existing types
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    DEFINES = "DEFINES"

    # Add your new type
    PROTECTS = "PROTECTS"      # Example: Middleware PROTECTS Route
    HANDLES = "HANDLES"         # Example: Route HANDLES Request
```

### 2. Create Node Builder Methods

**Location:** `aica/memory/graph_store/node_builder.py`

**Add builder method for your node type:**

```python
from aica.memory.graph_store.schema import NodeType


class NodeBuilder:
    """Builds node dictionaries for Neo4j."""

    # Existing methods...

    @staticmethod
    def build_middleware_node(
        middleware_data: dict,
        repo_path: Path
    ) -> dict:
        """Build a Middleware node from scanner data.

        Args:
            middleware_data: Dict from MiddlewareDetector with keys:
                - path: Relative file path
                - scope: "global" or "route"
                - directory: Parent directory
            repo_path: Absolute path to repository root.

        Returns:
            Node dict with id, labels, and properties.
        """
        file_path = repo_path / middleware_data["path"]

        return {
            "id": f"middleware:{middleware_data['path']}",
            "labels": [NodeType.MIDDLEWARE.value],
            "properties": {
                "path": middleware_data["path"],
                "name": file_path.stem,
                "scope": middleware_data["scope"],
                "directory": middleware_data["directory"],
                "absolute_path": str(file_path)
            }
        }
```

**Node ID conventions:**

- Use descriptive prefixes: `"middleware:app/middleware.ts"`
- Ensure uniqueness across all nodes
- Use path-based IDs for file-related nodes

**Properties guidelines:**

- Include all relevant metadata from scanner
- Always include `path` (relative) and `absolute_path`
- Add `name` for human-readable identification
- Use consistent property names across node types

### 3. Create Specialized Builder (Optional)

**Location:** `aica/memory/graph_store/{feature}_builder.py`

**For complex integration, create dedicated builder:**

```python
"""Builder for middleware graph nodes and relationships."""

from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger
from aica.memory.graph_store.node_builder import NodeBuilder
from aica.memory.graph_store.schema import NodeType, RelType

log = get_logger("graph.middleware_builder")


class MiddlewareBuilder:
    """Builds middleware nodes and relationships."""

    def __init__(self, neo4j_client) -> None:
        """Initialize with Neo4j client.

        Args:
            neo4j_client: Neo4jClient instance for database operations.
        """
        self.client = neo4j_client
        self.node_builder = NodeBuilder()

    def build_from_scanner(
        self,
        scanner_data: dict,
        repo_path: Path
    ) -> None:
        """Build middleware nodes and relationships from scanner output.

        Args:
            scanner_data: Full scanner output dict with 'middlewares' key.
            repo_path: Absolute path to repository root.
        """
        log.info("middleware.build_started", path=str(repo_path))

        middlewares = scanner_data.get("middlewares", [])

        # Create nodes
        for mw_data in middlewares:
            node = self.node_builder.build_middleware_node(mw_data, repo_path)
            self.client.create_node(node)

        # Create relationships
        self._create_middleware_relationships(middlewares, scanner_data, repo_path)

        log.debug("middleware.build_completed", count=len(middlewares))

    def _create_middleware_relationships(
        self,
        middlewares: list[dict],
        scanner_data: dict,
        repo_path: Path
    ) -> None:
        """Create relationships between middleware and other nodes.

        Args:
            middlewares: List of middleware data dicts.
            scanner_data: Full scanner output for cross-referencing.
            repo_path: Absolute path to repository root.
        """
        routes = scanner_data.get("routes", [])

        for mw in middlewares:
            mw_id = f"middleware:{mw['path']}"

            # Example: Global middleware protects all routes
            if mw["scope"] == "global":
                for route in routes:
                    route_id = f"route:{route['path']}"
                    self.client.create_relationship(
                        from_id=mw_id,
                        to_id=route_id,
                        rel_type=RelType.PROTECTS.value,
                        properties={"type": "global"}
                    )

            # Example: Route-specific middleware
            elif mw["scope"] == "route":
                # Find routes in same directory
                mw_dir = mw["directory"]
                for route in routes:
                    if route.get("directory") == mw_dir:
                        route_id = f"route:{route['path']}"
                        self.client.create_relationship(
                            from_id=mw_id,
                            to_id=route_id,
                            rel_type=RelType.PROTECTS.value,
                            properties={"type": "route-specific"}
                        )
```

### 4. Integrate with Graph Builder

**Location:** `aica/memory/graph_store/graph_builder.py`

**Add to orchestration:**

```python
from aica.memory.graph_store.middleware_builder import MiddlewareBuilder


class GraphBuilder:
    """Orchestrates the graph building process."""

    def build_graph(self, scanner_output: dict, repo_path: Path) -> None:
        """Build the complete repository knowledge graph.

        Args:
            scanner_output: Output from RepoScanner.
            repo_path: Absolute path to repository root.
        """
        log.info("graph.build_started", path=str(repo_path))

        # Existing builders
        scanner_builder = ScannerBuilder(self.client)
        scanner_builder.build_from_scanner(scanner_output, repo_path)

        import_builder = ImportBuilder(self.client)
        import_builder.build_from_ast(scanner_output, repo_path)

        # Add your new builder
        middleware_builder = MiddlewareBuilder(self.client)
        middleware_builder.build_from_scanner(scanner_output, repo_path)

        log.info("graph.build_completed", path=str(repo_path))
```

### 5. Create Neo4j Client Methods (If Needed)

**Location:** `aica/memory/graph_store/neo4j_client.py`

**Standard operations are usually sufficient:**

- `create_node(node_dict)` - Create single node
- `create_nodes(node_list)` - Batch create nodes
- `create_relationship(from_id, to_id, rel_type, properties)` - Create relationship
- `query(cypher, params)` - Execute raw Cypher

**Add specialized methods only if needed:**

```python
def find_middleware_for_route(self, route_path: str) -> list[dict]:
    """Find all middleware protecting a specific route.

    Args:
        route_path: Relative path to route file.

    Returns:
        List of middleware node dicts.
    """
    cypher = """
    MATCH (m:Middleware)-[r:PROTECTS]->(route:Route {path: $route_path})
    RETURN m, r.type as protection_type
    ORDER BY m.scope DESC
    """

    results = self.query(cypher, {"route_path": route_path})
    return [dict(record["m"]) for record in results]
```

### 6. Write Tests

**Location:** `tests/test_{feature}_builder.py`

**Test node creation:**

```python
"""Tests for MiddlewareBuilder."""

from pathlib import Path

import pytest

from aica.memory.graph_store.middleware_builder import MiddlewareBuilder
from aica.memory.graph_store.neo4j_client import Neo4jClient
from aica.memory.graph_store.schema import NodeType, RelType


@pytest.fixture
def mock_client(mocker):
    """Mock Neo4j client."""
    return mocker.Mock(spec=Neo4jClient)


@pytest.fixture
def builder(mock_client):
    """Create builder with mock client."""
    return MiddlewareBuilder(mock_client)


def test_build_middleware_nodes(builder, mock_client, tmp_path):
    """Test middleware nodes are created correctly."""
    scanner_data = {
        "middlewares": [
            {
                "path": "middleware.ts",
                "scope": "global",
                "directory": "."
            }
        ]
    }

    builder.build_from_scanner(scanner_data, tmp_path)

    # Verify node creation
    mock_client.create_node.assert_called_once()
    node = mock_client.create_node.call_args[0][0]

    assert node["labels"] == [NodeType.MIDDLEWARE.value]
    assert node["id"] == "middleware:middleware.ts"
    assert node["properties"]["scope"] == "global"


def test_create_middleware_relationships(builder, mock_client, tmp_path):
    """Test relationships are created between middleware and routes."""
    scanner_data = {
        "middlewares": [
            {"path": "middleware.ts", "scope": "global", "directory": "."}
        ],
        "routes": [
            {"path": "app/page.tsx", "route": "/", "directory": "app"}
        ]
    }

    builder.build_from_scanner(scanner_data, tmp_path)

    # Verify relationship creation
    mock_client.create_relationship.assert_called()
    call_args = mock_client.create_relationship.call_args[1]

    assert call_args["from_id"] == "middleware:middleware.ts"
    assert call_args["to_id"] == "route:app/page.tsx"
    assert call_args["rel_type"] == RelType.PROTECTS.value
```

### 7. Test with Real Neo4j

**Manual testing with local Neo4j:**

```python
from pathlib import Path
from aica.memory.graph_store.neo4j_client import Neo4jClient
from aica.memory.graph_store.middleware_builder import MiddlewareBuilder

# Connect to Neo4j
client = Neo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Load scanner output
import json
scanner_path = Path(".repo_intelligence/structure.json")
scanner_data = json.loads(scanner_path.read_text())

# Build graph
repo_path = Path(".")
builder = MiddlewareBuilder(client)
builder.build_from_scanner(scanner_data, repo_path)

print("Graph built successfully!")
```

**Verify in Neo4j Browser:**

```cypher
// View all middleware nodes
MATCH (m:Middleware)
RETURN m
LIMIT 25

// View middleware relationships
MATCH (m:Middleware)-[r:PROTECTS]->(route)
RETURN m, r, route
LIMIT 25

// Count by type
MATCH (m:Middleware)
RETURN m.scope, count(*) as count
ORDER BY count DESC
```

### 8. Build Useful Queries

**Location:** Create helper methods or document common queries

**Example analysis queries:**

```cypher
// Find all routes protected by global middleware
MATCH (m:Middleware {scope: 'global'})-[:PROTECTS]->(r:Route)
RETURN r.path, r.route
ORDER BY r.route

// Find routes without middleware
MATCH (r:Route)
WHERE NOT (r)<-[:PROTECTS]-(:Middleware)
RETURN r.path, r.route

// Middleware dependency chain
MATCH path = (m:Middleware)-[:IMPORTS*1..3]->(dep)
RETURN path
LIMIT 10

// Find most protected routes
MATCH (m:Middleware)-[:PROTECTS]->(r:Route)
WITH r, count(m) as middleware_count
RETURN r.path, middleware_count
ORDER BY middleware_count DESC
LIMIT 10
```

## Quality Checklist

Before considering schema extension complete:

- [ ] Node type added to `NodeType` enum
- [ ] Relationship type added to `RelType` enum (if needed)
- [ ] Node builder method created in `node_builder.py`
- [ ] Specialized builder created (if complex logic needed)
- [ ] Integration added to `graph_builder.py`
- [ ] Tests written with >80% coverage
- [ ] Manual testing with real Neo4j completed
- [ ] Nodes appear correctly in Neo4j Browser
- [ ] Relationships are created as expected
- [ ] Query performance is acceptable
- [ ] Documentation updated with example queries
- [ ] No duplicate nodes created

## Common Pitfalls

❌ **Non-unique node IDs:**

```python
node_id = "middleware"  # Will create duplicates!
```

✅ **Unique IDs with path:**

```python
node_id = f"middleware:{middleware_data['path']}"
```

❌ **Missing relationship direction:**

```cypher
MATCH (a)-[:PROTECTS]-(b)  # Matches both directions
```

✅ **Explicit direction:**

```cypher
MATCH (a)-[:PROTECTS]->(b)  # a protects b
```

❌ **Not handling missing scanner data:**

```python
middlewares = scanner_data["middlewares"]  # KeyError if missing!
```

✅ **Safe access with default:**

```python
middlewares = scanner_data.get("middlewares", [])
```

❌ **Creating relationships before nodes:**

```python
# This will fail if nodes don't exist yet
client.create_relationship(from_id, to_id, rel_type)
```

✅ **Create nodes first, then relationships:**

```python
client.create_node(node1)
client.create_node(node2)
client.create_relationship(node1_id, node2_id, rel_type)
```

## Performance Tips

### Batch Operations

```python
# ❌ Slow: One transaction per node
for node_data in nodes:
    client.create_node(node_data)

# ✅ Fast: Batch create in single transaction
client.create_nodes(nodes)
```

### Index Creation

```cypher
// Create indexes for frequently queried properties
CREATE INDEX middleware_path IF NOT EXISTS FOR (m:Middleware) ON (m.path);
CREATE INDEX middleware_scope IF NOT EXISTS FOR (m:Middleware) ON (m.scope);
```

### Relationship Properties

```python
# Keep relationship properties minimal
client.create_relationship(
    from_id=mw_id,
    to_id=route_id,
    rel_type=RelType.PROTECTS.value,
    properties={"type": "global"}  # Just essential metadata
)
```

## Related Resources

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [Schema Definitions](../../aica/memory/graph_store/schema.py)
- [Node Builder](../../aica/memory/graph_store/node_builder.py)
- [Neo4j Client](../../aica/memory/graph_store/neo4j_client.py)
- [Existing Builders](../../aica/memory/graph_store/) - Reference implementations

## Example Invocation

```
/graph-schema-extension Add middleware nodes and protection relationships
```
