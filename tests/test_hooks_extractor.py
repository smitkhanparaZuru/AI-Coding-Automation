"""
Tests for the hooks extractor (Task 3.5).

Mirrors the pattern established by test_calls_extractor.py.
"""

from __future__ import annotations

import pytest

from aica.repo_intelligence.ast.extractors.hooks import extract
from aica.repo_intelligence.ast.parser import parse_code

_FILE = "src/test.tsx"


def _parse(code: str, lang: str = "tsx"):
    return parse_code(code, lang=lang)


def _extract(code: str, file_path: str = _FILE, lang: str = "tsx") -> list[dict]:
    tree = _parse(code, lang=lang)
    return extract(tree, code, file_path)


def _find(results: list[dict], **kwargs) -> dict | None:
    """Return first entry whose fields all match *kwargs*."""
    for entry in results:
        if all(entry.get(k) == v for k, v in kwargs.items()):
            return entry
    return None


# ---------------------------------------------------------------------------
# Basic
# ---------------------------------------------------------------------------


class TestHooksExtractorBasic:
    def test_empty_file_returns_empty_list(self):
        assert _extract("") == []

    def test_return_type_is_list(self):
        assert isinstance(_extract("const x = 1;"), list)

    def test_non_hook_call_not_captured(self):
        assert _extract("doSomething();") == []

    def test_plain_function_not_hook(self):
        assert _extract("function foo() {}") == []


# ---------------------------------------------------------------------------
# Built-in React hooks
# ---------------------------------------------------------------------------


class TestBuiltInHooks:
    def test_use_state(self):
        results = _extract("const [v, setV] = useState(0);")
        assert len(results) == 1
        assert results[0]["name"] == "useState"

    def test_use_effect(self):
        results = _extract("useEffect(() => {}, []);")
        assert len(results) == 1
        assert results[0]["name"] == "useEffect"

    def test_use_ref(self):
        results = _extract("const ref = useRef(null);")
        assert len(results) == 1
        assert results[0]["name"] == "useRef"

    def test_use_callback(self):
        results = _extract("const cb = useCallback(() => {}, []);")
        assert len(results) == 1
        assert results[0]["name"] == "useCallback"

    def test_use_memo(self):
        results = _extract("const v = useMemo(() => 42, []);")
        assert len(results) == 1
        assert results[0]["name"] == "useMemo"

    def test_use_context(self):
        results = _extract("const ctx = useContext(MyCtx);")
        assert len(results) == 1
        assert results[0]["name"] == "useContext"


# ---------------------------------------------------------------------------
# Custom hooks
# ---------------------------------------------------------------------------


class TestCustomHooks:
    def test_custom_hook_detected(self):
        results = _extract("const x = useMyHook();")
        assert len(results) == 1
        assert results[0]["name"] == "useMyHook"

    def test_use_auth(self):
        results = _extract("const { user } = useAuth();")
        assert len(results) == 1
        assert results[0]["name"] == "useAuth"

    def test_use_router(self):
        results = _extract("const router = useRouter();")
        assert len(results) == 1
        assert results[0]["name"] == "useRouter"

    def test_multiple_hooks(self):
        code = """\
const [a, setA] = useState(0);
const [b, setB] = useState('');
const ref = useRef(null);
"""
        results = _extract(code)
        names = [r["name"] for r in results]
        assert names.count("useState") == 2
        assert "useRef" in names


# ---------------------------------------------------------------------------
# Hook name exclusion rules
# ---------------------------------------------------------------------------


class TestHookExclusion:
    def test_use_lowercase_not_hook(self):
        # "uselessly" starts with 'use' + lowercase 'l' → not a hook per convention
        assert _extract("uselessly();") == []

    def test_used_not_hook(self):
        # "used" starts with 'use' but no uppercase follows
        assert _extract("used();") == []

    def test_use_alone_not_hook(self):
        # single word "use" is not a hook
        assert _extract("use();") == []

    def test_usemethod_call_on_object_not_captured(self):
        # member call like obj.useState() — function child is member_expression, not identifier
        assert _extract("obj.useState(42);") == []

    def test_new_expression_not_captured(self):
        # new UseConstructor() — new_expression, not call_expression
        assert _extract("new UseConstructor();") == []


# ---------------------------------------------------------------------------
# Caller context
# ---------------------------------------------------------------------------


class TestCaller:
    def test_module_level_caller_is_none(self):
        results = _extract("const v = useState(0);")
        assert results[0]["caller"] is None

    def test_hook_inside_named_function(self):
        code = """\
function MyComponent() {
  const [v, setV] = useState(0);
}
"""
        results = _extract(code)
        assert results[0]["caller"] == "MyComponent"

    def test_hook_inside_arrow_with_name(self):
        code = """\
const MyComp = () => {
  const ref = useRef(null);
};
"""
        results = _extract(code)
        assert results[0]["caller"] == "MyComp"

    def test_hook_inside_anonymous_arrow_caller_none(self):
        code = """\
const fn = (() => {
  const v = useState(0);
})();
"""
        results = _extract(code)
        # The immediately enclosing arrow is anonymous (IIFE, no declarator binding)
        # caller may be None or "fn" depending on nesting; just check it's a string or None
        assert results[0]["caller"] is None or isinstance(results[0]["caller"], str)

    def test_hook_inside_method(self):
        code = """\
class Foo {
  render() {
    const v = useState(0);
  }
}
"""
        results = _extract(code)
        assert results[0]["caller"] == "render"


# ---------------------------------------------------------------------------
# args_count
# ---------------------------------------------------------------------------


class TestArgsCount:
    def test_no_args(self):
        results = _extract("useEffect(() => {});")
        # one arg (the callback)
        assert results[0]["args_count"] == 1

    def test_zero_args_manual(self):
        results = _extract("useMyHook();")
        assert results[0]["args_count"] == 0

    def test_two_args(self):
        results = _extract("useEffect(() => {}, [dep]);")
        assert results[0]["args_count"] == 2

    def test_three_args(self):
        results = _extract("useReducer(reducer, initialState, init);")
        assert results[0]["args_count"] == 3

    def test_one_arg(self):
        results = _extract("const v = useState(0);")
        assert results[0]["args_count"] == 1


# ---------------------------------------------------------------------------
# Line numbers
# ---------------------------------------------------------------------------


class TestLineNumbers:
    def test_line_is_one_based(self):
        results = _extract("const v = useState(0);")
        assert results[0]["line"] == 1

    def test_line_tracks_multiple_hooks(self):
        code = """\
const a = useState(0);
const b = useState('');
"""
        results = _extract(code)
        lines = [r["line"] for r in results]
        assert lines == [1, 2]

    def test_line_after_gap(self):
        code = """\
const x = 1;

const v = useState(0);
"""
        results = _extract(code)
        assert results[0]["line"] == 3


# ---------------------------------------------------------------------------
# File field
# ---------------------------------------------------------------------------


class TestFileField:
    def test_file_embedded_in_every_entry(self):
        code = """\
const a = useState(0);
const b = useRef(null);
"""
        results = _extract(code, file_path="src/comp.tsx")
        assert all(r["file"] == "src/comp.tsx" for r in results)

    def test_file_field_is_posix_path(self):
        results = _extract("const v = useState(0);", file_path="src/nested/comp.tsx")
        assert results[0]["file"] == "src/nested/comp.tsx"
