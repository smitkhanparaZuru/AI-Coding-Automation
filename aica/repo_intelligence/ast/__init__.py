"""
AST parsing module for TypeScript / TSX source files.

Provides tree-sitter-backed parsing for function-level and dependency-level
code understanding. This is the foundation for Phase 3 extractors.

Public API
----------
parse_code(code, lang)   -- parse a source-code string
parse_file(file_path)    -- read a file and parse it (auto-detects grammar)
"""

from aica.repo_intelligence.ast.parser import parse_code, parse_file

__all__ = ["parse_code", "parse_file"]
