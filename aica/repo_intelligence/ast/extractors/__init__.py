"""
Extractors package — Phase 3.2+

Each extractor module walks a tree-sitter parse Tree and extracts one
category of code intelligence. All extractors follow the same contract:

    extract(tree: Tree, source: str, file_path: str) -> list[dict]


    imports     — import statements, module kind, named/default/namespace bindings
    functions   — function declarations, arrow functions, generators, class methods
    exports     — named, default, re-export, and namespace re-export statements
    calls       — per-file function call graph (callee names, caller context, kind)
                  build_call_graph() transforms flat rows to grouped JSON structure
    hooks       — React useX hook invocations (name, caller, args_count)
    components  — React component definitions (kind, props, exported)
    types       — interface and type alias declarations (kind, members, exported)
"""

from aica.repo_intelligence.ast.extractors.calls import build_call_graph
from aica.repo_intelligence.ast.extractors.calls import extract as extract_calls
from aica.repo_intelligence.ast.extractors.components import extract as extract_components
from aica.repo_intelligence.ast.extractors.exports import extract as extract_exports
from aica.repo_intelligence.ast.extractors.functions import extract as extract_functions
from aica.repo_intelligence.ast.extractors.hooks import extract as extract_hooks
from aica.repo_intelligence.ast.extractors.imports import extract as extract_imports
from aica.repo_intelligence.ast.extractors.types import extract as extract_types

__all__ = [
    "extract_imports",
    "extract_functions",
    "extract_exports",
    "extract_calls",
    "build_call_graph",
    "extract_hooks",
    "extract_components",
    "extract_types",
]
