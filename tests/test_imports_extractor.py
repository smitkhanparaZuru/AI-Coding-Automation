"""
Tests for aica.repo_intelligence.ast.extractors.imports

Covers:
    extract() — default, named, namespace, side-effect, type-only imports
    import_kind — relative / alias / external classification
    named import aliases — {"name": str, "alias": str | None}
    file field — embedded in every output dict
    line numbers — 1-based
    multiple import statements — order preserved
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.imports import extract
from aica.repo_intelligence.ast.parser import parse_code

_FILE = "src/test.ts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(code: str, lang: str = "typescript"):
    return parse_code(code, lang=lang)


def _extract(code: str, file_path: str = _FILE, lang: str = "typescript") -> list[dict]:
    tree = _parse(code, lang=lang)
    return extract(tree, code, file_path)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


class TestImportsExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_returns_list(self):
        result = _extract("import React from 'react';")
        assert isinstance(result, list)

    def test_non_import_code_returns_empty_list(self):
        result = _extract("const x = 1;\nfunction foo() {}")
        assert result == []


# ---------------------------------------------------------------------------
# Default import
# ---------------------------------------------------------------------------


class TestDefaultImport:
    def test_default_binding(self):
        result = _extract("import React from 'react';")
        assert len(result) == 1
        assert result[0]["default"] == "React"

    def test_source(self):
        result = _extract("import React from 'react';")
        assert result[0]["source"] == "react"

    def test_not_side_effect(self):
        result = _extract("import React from 'react';")
        assert result[0]["side_effect"] is False

    def test_not_type_only(self):
        result = _extract("import React from 'react';")
        assert result[0]["type_only"] is False

    def test_named_is_empty(self):
        result = _extract("import React from 'react';")
        assert result[0]["named"] == []

    def test_namespace_is_none(self):
        result = _extract("import React from 'react';")
        assert result[0]["namespace"] is None

    def test_line_number_one_based(self):
        result = _extract("import React from 'react';")
        assert result[0]["line"] == 1


# ---------------------------------------------------------------------------
# Named imports (no aliases)
# ---------------------------------------------------------------------------


class TestNamedImports:
    def test_single_named(self):
        result = _extract("import { foo } from './utils';")
        assert len(result[0]["named"]) == 1
        assert result[0]["named"][0]["name"] == "foo"
        assert result[0]["named"][0]["alias"] is None

    def test_multiple_named(self):
        result = _extract("import { a, b, c } from './mod';")
        names = [n["name"] for n in result[0]["named"]]
        assert names == ["a", "b", "c"]

    def test_multiple_named_no_aliases(self):
        result = _extract("import { useState, useEffect } from 'react';")
        for entry in result[0]["named"]:
            assert entry["alias"] is None

    def test_default_is_none_for_named_only(self):
        result = _extract("import { foo } from './utils';")
        assert result[0]["default"] is None


# ---------------------------------------------------------------------------
# Named import aliases  import { foo as bar }
# ---------------------------------------------------------------------------


class TestNamedImportAlias:
    def test_alias_captured(self):
        result = _extract("import { foo as bar } from './utils';")
        named = result[0]["named"]
        assert len(named) == 1
        assert named[0]["name"] == "foo"
        assert named[0]["alias"] == "bar"

    def test_no_alias_is_null(self):
        result = _extract("import { foo } from './utils';")
        assert result[0]["named"][0]["alias"] is None

    def test_mixed_alias_and_plain(self):
        result = _extract("import { a, b as B } from './mod';")
        named = result[0]["named"]
        plain = next(n for n in named if n["name"] == "a")
        aliased = next(n for n in named if n["name"] == "b")
        assert plain["alias"] is None
        assert aliased["alias"] == "B"


# ---------------------------------------------------------------------------
# Namespace import   import * as X from '...'
# ---------------------------------------------------------------------------


class TestNamespaceImport:
    def test_namespace_captured(self):
        result = _extract("import * as Utils from './utils';")
        assert result[0]["namespace"] == "Utils"

    def test_named_empty_for_namespace(self):
        result = _extract("import * as Utils from './utils';")
        assert result[0]["named"] == []

    def test_default_none_for_namespace(self):
        result = _extract("import * as Utils from './utils';")
        assert result[0]["default"] is None


# ---------------------------------------------------------------------------
# Side-effect import   import './styles.css'
# ---------------------------------------------------------------------------


class TestSideEffectImport:
    def test_side_effect_flag(self):
        result = _extract("import './styles.css';")
        assert result[0]["side_effect"] is True

    def test_default_none(self):
        result = _extract("import './styles.css';")
        assert result[0]["default"] is None

    def test_named_empty(self):
        result = _extract("import './styles.css';")
        assert result[0]["named"] == []

    def test_namespace_none(self):
        result = _extract("import './styles.css';")
        assert result[0]["namespace"] is None

    def test_source_captured(self):
        result = _extract("import './styles.css';")
        assert result[0]["source"] == "./styles.css"


# ---------------------------------------------------------------------------
# Type-only import   import type { Foo } from '...'
# ---------------------------------------------------------------------------


class TestTypeOnlyImport:
    def test_type_only_flag(self):
        result = _extract("import type { Foo } from './types';")
        assert result[0]["type_only"] is True

    def test_named_captured_for_type_import(self):
        result = _extract("import type { Foo } from './types';")
        assert any(n["name"] == "Foo" for n in result[0]["named"])

    def test_regular_import_not_type_only(self):
        result = _extract("import { Foo } from './types';")
        assert result[0]["type_only"] is False


# ---------------------------------------------------------------------------
# import_kind classification
# ---------------------------------------------------------------------------


class TestImportKind:
    def test_relative_dot_slash(self):
        result = _extract("import { x } from './utils';")
        assert result[0]["import_kind"] == "relative"

    def test_relative_dot_dot_slash(self):
        result = _extract("import { x } from '../types';")
        assert result[0]["import_kind"] == "relative"

    def test_alias_at_sign(self):
        result = _extract("import { x } from '@/hooks/useUser';")
        assert result[0]["import_kind"] == "alias"

    def test_alias_tilde(self):
        result = _extract("import { x } from '~/utils';")
        assert result[0]["import_kind"] == "alias"

    def test_external_npm(self):
        result = _extract("import React from 'react';")
        assert result[0]["import_kind"] == "external"

    def test_external_scoped_package(self):
        # @scope/package is an alias by our rule since it starts with @
        result = _extract("import { x } from 'lodash';")
        assert result[0]["import_kind"] == "external"


# ---------------------------------------------------------------------------
# Mixed default + named
# ---------------------------------------------------------------------------


class TestMixedImport:
    def test_default_and_named(self):
        result = _extract("import React, { useState } from 'react';")
        assert result[0]["default"] == "React"
        assert any(n["name"] == "useState" for n in result[0]["named"])

    def test_default_and_named_no_alias(self):
        result = _extract("import React, { useState } from 'react';")
        named = result[0]["named"]
        assert named[0]["alias"] is None


# ---------------------------------------------------------------------------
# file field
# ---------------------------------------------------------------------------


class TestFileField:
    def test_file_embedded_in_every_entry(self):
        code = "import React from 'react';\nimport { x } from './x';"
        result = _extract(code, file_path="src/Button.tsx")
        assert all(e["file"] == "src/Button.tsx" for e in result)

    def test_file_matches_argument(self):
        result = _extract("import './init';", file_path="custom/path.ts")
        assert result[0]["file"] == "custom/path.ts"


# ---------------------------------------------------------------------------
# Multiple import statements
# ---------------------------------------------------------------------------


class TestMultipleImports:
    def test_count(self):
        code = (
            "import React from 'react';\n"
            "import { useState } from 'react';\n"
            "import './styles.css';\n"
        )
        result = _extract(code)
        assert len(result) == 3

    def test_order_preserved(self):
        code = (
            "import A from 'a';\n"
            "import B from 'b';\n"
            "import C from 'c';\n"
        )
        result = _extract(code)
        assert [r["source"] for r in result] == ["a", "b", "c"]

    def test_line_numbers_sequential(self):
        code = (
            "import A from 'a';\n"
            "import B from 'b';\n"
        )
        result = _extract(code)
        assert result[0]["line"] == 1
        assert result[1]["line"] == 2
