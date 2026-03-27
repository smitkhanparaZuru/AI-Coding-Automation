---
name: ast-extractor-workflow
description: 'Workflow for creating AST extractors to parse TypeScript/JavaScript code in AICA. Use when: adding new extractor, parsing code patterns, extracting imports/exports/functions/types, analyzing code structure, implementing AST visitors.'
argument-hint: 'Describe what to extract (e.g., "extract React hooks", "parse decorators")'
---

# AST Extractor Workflow

Complete workflow for creating AST extractors that parse TypeScript/JavaScript code patterns in AICA.

## When to Use

- Adding new AST extractor for TypeScript/JavaScript patterns
- Parsing specific code constructs (imports, exports, functions, hooks, etc.)
- Extracting metadata from source code
- Analyzing code structure and relationships
- Implementing custom AST visitors

## Prerequisites

- Understanding of Abstract Syntax Trees (AST) concepts
- Familiarity with TypeScript/JavaScript syntax
- Knowledge of the `tree-sitter` library
- Understanding of the target code pattern to extract

## Architecture Overview

AICA's AST system:

```
Source File → Tree-sitter Parser → AST → Extractors → Structured Data
```

**Key components:**

- `parser.py` - Parses files into AST using tree-sitter
- `extractors/` - Individual extractors for specific patterns
- `runner.py` - Orchestrates extraction process
- `writer.py` - Writes extracted data to JSON

## Workflow Steps

### 1. Understand the Target Pattern

**Identify what to extract:**

- Import statements and their sources
- Export declarations (named, default)
- Function definitions and signatures
- Class declarations and methods
- Type definitions and interfaces
- React hooks usage
- Decorators or annotations
- Custom patterns specific to framework

**Example patterns:**

```typescript
// Import patterns
import { useState } from 'react'
import type { User } from './types'

// Export patterns
export const fetchUser = async () => {}
export default function Page() {}

// Function patterns
function handleClick(event: Event): void {}
const arrow = () => {}

// Hook patterns
const [state, setState] = useState(0)
const data = useSWR('/api/user')

// Type patterns
interface User { name: string }
type Status = 'active' | 'inactive'
```

### 2. Explore AST Structure

**Use tree-sitter playground to understand node types:**

```python
# Quick script to explore AST
from tree_sitter import Language, Parser
import tree_sitter_typescript as ts_typescript

# Initialize parser
TS_LANGUAGE = Language(ts_typescript.language_typescript())
parser = Parser()
parser.set_language(TS_LANGUAGE)

# Parse sample code
code = b"""
import { useState } from 'react'
export const MyComponent = () => {}
"""

tree = parser.parse(code)
root = tree.root_node

# Print AST structure
def print_tree(node, depth=0):
    print("  " * depth + f"{node.type}: {node.text[:50] if node.text else ''}")
    for child in node.children:
        print_tree(child, depth + 1)

print_tree(root)
```

**Common node types:**

- `import_statement` - Import declarations
- `export_statement` - Export declarations
- `function_declaration` - Named functions
- `arrow_function` - Arrow functions
- `call_expression` - Function calls
- `interface_declaration` - TypeScript interfaces
- `type_alias_declaration` - Type definitions
- `identifier` - Variable/function names

### 3. Create Extractor File

**Location:** `aica/repo_intelligence/ast/extractors/{name}_extractor.py`

**Template:**

```python
"""Extractor for [pattern description]."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from aica.core.logging import get_logger

log = get_logger("ast.{name}_extractor")


class {Name}Extractor:
    """Extract [pattern] from TypeScript/JavaScript AST.

    Returns:
        list[dict]: List of extracted [items] with metadata.
        Each dict contains:
        - name: Identifier name
        - [other fields as needed]
    """

    def extract(self, root_node: Node, file_path: Path) -> list[dict]:
        """Extract [pattern] from AST.

        Args:
            root_node: Root node of the AST.
            file_path: Path to source file (for context).

        Returns:
            List of dicts with extracted data.
        """
        log.debug("extraction.started", file=str(file_path))

        results = []
        self._traverse(root_node, results, file_path)

        log.debug("extraction.completed", file=str(file_path), count=len(results))
        return results

    def _traverse(self, node: Node, results: list[dict], file_path: Path) -> None:
        """Recursively traverse AST to find target patterns.

        Args:
            node: Current AST node.
            results: List to append extracted data to.
            file_path: Source file path.
        """
        # Check if this node matches our pattern
        if node.type == "target_node_type":
            extracted = self._extract_from_node(node, file_path)
            if extracted:
                results.append(extracted)

        # Recurse into children
        for child in node.children:
            self._traverse(child, results, file_path)

    def _extract_from_node(self, node: Node, file_path: Path) -> dict | None:
        """Extract data from a matching node.

        Args:
            node: AST node matching target pattern.
            file_path: Source file path.

        Returns:
            Dict with extracted data, or None if extraction failed.
        """
        try:
            # Extract required information
            name = self._get_identifier(node)

            return {
                "name": name,
                "file": str(file_path),
                "line": node.start_point[0] + 1,
                "type": node.type
            }
        except Exception as e:
            log.warning("extraction.failed", node_type=node.type, error=str(e))
            return None

    def _get_identifier(self, node: Node) -> str:
        """Extract identifier name from node.

        Args:
            node: AST node containing identifier.

        Returns:
            Identifier name as string.
        """
        # Find identifier child node
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
        return "unknown"
```

### 4. Implement Common Extraction Patterns

**Find specific child nodes:**

```python
def _find_child_by_type(self, node: Node, child_type: str) -> Node | None:
    """Find first child node of specific type.

    Args:
        node: Parent node to search in.
        child_type: Type of child node to find.

    Returns:
        First matching child node, or None.
    """
    for child in node.children:
        if child.type == child_type:
            return child
    return None
```

**Extract text from node:**

```python
def _get_node_text(self, node: Node) -> str:
    """Get text content of node.

    Args:
        node: AST node.

    Returns:
        Node text as string.
    """
    if node.text:
        return node.text.decode("utf-8")
    return ""
```

**Get line and column numbers:**

```python
def _get_location(self, node: Node) -> dict:
    """Get location information for node.

    Args:
        node: AST node.

    Returns:
        Dict with line and column info (1-indexed).
    """
    return {
        "line": node.start_point[0] + 1,
        "column": node.start_point[1] + 1,
        "end_line": node.end_point[0] + 1,
        "end_column": node.end_point[1] + 1
    }
```

**Extract named children:**

```python
def _get_named_children(self, node: Node) -> list[Node]:
    """Get all named children (ignoring punctuation).

    Args:
        node: Parent node.

    Returns:
        List of named child nodes.
    """
    return [child for child in node.children if child.is_named]
```

### 5. Example: Import Extractor

**Real-world example:**

```python
"""Extractor for import statements."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from aica.core.logging import get_logger

log = get_logger("ast.imports_extractor")


class ImportsExtractor:
    """Extract import statements from TypeScript/JavaScript files."""

    def extract(self, root_node: Node, file_path: Path) -> list[dict]:
        """Extract all import statements.

        Args:
            root_node: Root node of AST.
            file_path: Path to source file.

        Returns:
            List of import dicts with keys:
            - source: Import source path
            - imports: List of imported identifiers
            - is_type_only: Whether it's a type-only import
            - line: Line number
        """
        log.debug("extraction.started", file=str(file_path))

        results = []
        self._traverse(root_node, results, file_path)

        log.debug("extraction.completed", file=str(file_path), count=len(results))
        return results

    def _traverse(self, node: Node, results: list[dict], file_path: Path) -> None:
        """Find import_statement nodes."""
        if node.type == "import_statement":
            import_data = self._extract_import(node, file_path)
            if import_data:
                results.append(import_data)

        for child in node.children:
            self._traverse(child, results, file_path)

    def _extract_import(self, node: Node, file_path: Path) -> dict | None:
        """Extract data from import_statement node.

        Handles patterns:
        - import { Name } from 'source'
        - import Name from 'source'
        - import * as Name from 'source'
        - import type { Type } from 'source'
        """
        try:
            source = self._get_import_source(node)
            imports = self._get_imported_names(node)
            is_type_only = self._is_type_import(node)

            return {
                "source": source,
                "imports": imports,
                "is_type_only": is_type_only,
                "line": node.start_point[0] + 1,
                "file": str(file_path)
            }
        except Exception as e:
            log.warning("import.extraction_failed", error=str(e))
            return None

    def _get_import_source(self, node: Node) -> str:
        """Extract source path from import statement."""
        for child in node.children:
            if child.type == "string":
                # Remove quotes
                text = child.text.decode("utf-8")
                return text.strip('"\'')
        return ""

    def _get_imported_names(self, node: Node) -> list[str]:
        """Extract imported identifier names."""
        imports = []

        for child in node.children:
            if child.type == "import_clause":
                imports.extend(self._extract_from_import_clause(child))

        return imports

    def _extract_from_import_clause(self, node: Node) -> list[str]:
        """Extract names from import clause."""
        names = []

        for child in node.children:
            if child.type == "identifier":
                # Default import
                names.append(child.text.decode("utf-8"))
            elif child.type == "named_imports":
                # Named imports like { A, B }
                for spec in child.children:
                    if spec.type == "import_specifier":
                        name = self._get_identifier(spec)
                        if name:
                            names.append(name)
            elif child.type == "namespace_import":
                # import * as Name
                name = self._get_identifier(child)
                if name:
                    names.append(name)

        return names

    def _is_type_import(self, node: Node) -> bool:
        """Check if import is type-only (import type ...)."""
        text = node.text.decode("utf-8")
        return text.startswith("import type")

    def _get_identifier(self, node: Node) -> str | None:
        """Get identifier from node or its children."""
        if node.type == "identifier":
            return node.text.decode("utf-8")

        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")

        return None
```

### 6. Integrate with Runner

**Location:** `aica/repo_intelligence/ast/runner.py`

**Add extractor to runner:**

```python
from aica.repo_intelligence.ast.extractors.{name}_extractor import {Name}Extractor


class ASTRunner:
    """Runs AST extraction on repository files."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.parser = ASTParser()

        # Initialize extractors
        self.extractors = {
            "imports": ImportsExtractor(),
            "exports": ExportsExtractor(),
            "{name}": {Name}Extractor(),  # Add your extractor
        }

    def run(self) -> dict:
        """Run all extractors on repository.

        Returns:
            Dict with extracted data from all extractors.
        """
        results = {
            "imports": [],
            "exports": [],
            "{name}": [],  # Add field for your data
        }

        # Find all TypeScript/JavaScript files
        patterns = ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
        files = []
        for pattern in patterns:
            files.extend(self.repo_path.rglob(pattern))

        # Run extractors on each file
        for file_path in files:
            if "node_modules" in file_path.parts:
                continue

            tree = self.parser.parse_file(file_path)
            if tree:
                for name, extractor in self.extractors.items():
                    extracted = extractor.extract(tree.root_node, file_path)
                    results[name].extend(extracted)

        return results
```

### 7. Write Tests

**Location:** `tests/test_{name}_extractor.py`

**Template:**

```python
"""Tests for {Name}Extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.ast.parser import ASTParser
from aica.repo_intelligence.ast.extractors.{name}_extractor import {Name}Extractor


@pytest.fixture
def parser():
    """Create AST parser."""
    return ASTParser()


@pytest.fixture
def extractor():
    """Create extractor instance."""
    return {Name}Extractor()


def test_extract_basic_pattern(tmp_path: Path, parser, extractor):
    """Test extractor finds basic pattern."""
    # Create test file
    code = """
    // Your test code here
    const example = () => {}
    """

    file_path = tmp_path / "test.ts"
    file_path.write_text(code)

    # Parse and extract
    tree = parser.parse_file(file_path)
    result = extractor.extract(tree.root_node, file_path)

    # Assert
    assert len(result) == 1
    assert result[0]["name"] == "example"


def test_extract_multiple_items(tmp_path: Path, parser, extractor):
    """Test extractor finds multiple items."""
    code = """
    function first() {}
    function second() {}
    """

    file_path = tmp_path / "test.ts"
    file_path.write_text(code)

    tree = parser.parse_file(file_path)
    result = extractor.extract(tree.root_node, file_path)

    assert len(result) == 2
    assert {r["name"] for r in result} == {"first", "second"}


def test_extract_with_types(tmp_path: Path, parser, extractor):
    """Test extractor handles TypeScript types."""
    code = """
    interface User {
        name: string;
    }
    """

    file_path = tmp_path / "test.ts"
    file_path.write_text(code)

    tree = parser.parse_file(file_path)
    result = extractor.extract(tree.root_node, file_path)

    # Assert based on what your extractor should find
    assert len(result) >= 0


def test_handles_invalid_syntax(tmp_path: Path, parser, extractor):
    """Test extractor handles syntax errors gracefully."""
    code = """
    const broken = (
    """

    file_path = tmp_path / "test.ts"
    file_path.write_text(code)

    tree = parser.parse_file(file_path)
    result = extractor.extract(tree.root_node, file_path)

    # Should not crash, may return empty or partial results
    assert isinstance(result, list)
```

### 8. Manual Testing

**Create test script:**

```python
from pathlib import Path
from aica.repo_intelligence.ast.parser import ASTParser
from aica.repo_intelligence.ast.extractors.{name}_extractor import {Name}Extractor

# Parse a real file
parser = ASTParser()
extractor = {Name}Extractor()

file_path = Path("path/to/your/test/file.ts")
tree = parser.parse_file(file_path)

if tree:
    results = extractor.extract(tree.root_node, file_path)

    print(f"Found {len(results)} items:")
    for item in results:
        print(f"  - {item}")
else:
    print("Failed to parse file")
```

## Quality Checklist

Before considering extractor complete:

- [ ] Extractor file created in `aica/repo_intelligence/ast/extractors/`
- [ ] Follows extractor pattern (takes `Node` and `Path`, returns `list[dict]`)
- [ ] Uses structured logging with `get_logger("ast.{name}_extractor")`
- [ ] Handles malformed code gracefully (no crashes)
- [ ] Integrated into `ast/runner.py`
- [ ] Test file created with >80% coverage
- [ ] Tests cover basic patterns, multiple items, edge cases
- [ ] Manual testing with real files completed
- [ ] Example output documented in docstring
- [ ] Recursive traversal works correctly

## Common Pitfalls

❌ **Not handling None values:**

```python
name = node.text.decode()  # Crashes if node.text is None
```

✅ **Safe access:**

```python
name = node.text.decode("utf-8") if node.text else "unknown"
```

❌ **Forgetting to recurse:**

```python
def _traverse(self, node: Node, results: list[dict]) -> None:
    if node.type == "target":
        results.append(self._extract(node))
    # Missing: for child in node.children: ...
```

✅ **Complete traversal:**

```python
def _traverse(self, node: Node, results: list[dict]) -> None:
    if node.type == "target":
        results.append(self._extract(node))

    for child in node.children:
        self._traverse(child, results)
```

❌ **Hardcoding expected structure:**

```python
identifier = node.children[2]  # Breaks if structure changes
```

✅ **Search by type:**

```python
identifier = self._find_child_by_type(node, "identifier")
```

## Performance Tips

### Avoid Deep Recursion

```python
# For very large files, use iterative traversal
def _traverse_iterative(self, root: Node, results: list[dict]) -> None:
    """Non-recursive traversal to avoid stack overflow."""
    stack = [root]

    while stack:
        node = stack.pop()

        if node.type == "target_type":
            results.append(self._extract(node))

        stack.extend(reversed(node.children))
```

### Cache Node Lookups

```python
# Cache frequently accessed patterns
self._identifier_cache = {}

def _get_cached_identifier(self, node: Node) -> str:
    """Get identifier with caching."""
    node_id = id(node)

    if node_id not in self._identifier_cache:
        self._identifier_cache[node_id] = self._get_identifier(node)

    return self._identifier_cache[node_id]
```

## Related Resources

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [AST Parser](../../aica/repo_intelligence/ast/parser.py)
- [Existing Extractors](../../aica/repo_intelligence/ast/extractors/)
- [AST Runner](../../aica/repo_intelligence/ast/runner.py)

## Example Invocation

```
/ast-extractor-workflow Create extractor for React hooks usage
```
