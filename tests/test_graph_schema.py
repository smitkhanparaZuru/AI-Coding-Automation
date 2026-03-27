from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from aica.memory.graph_store.schema import (
    CONSTRAINT_QUERIES,
    NodeLabel,
    RelType,
    setup_schema,
)

# ---------------------------------------------------------------------------
# NodeLabel
# ---------------------------------------------------------------------------


class TestNodeLabel:
    def test_member_count(self) -> None:
        assert len(NodeLabel) == 9

    def test_file(self) -> None:
        assert NodeLabel.FILE == "File"
        assert NodeLabel.FILE.value == "File"

    def test_function(self) -> None:
        assert NodeLabel.FUNCTION == "Function"

    def test_component(self) -> None:
        assert NodeLabel.COMPONENT == "Component"

    def test_hook(self) -> None:
        assert NodeLabel.HOOK == "Hook"

    def test_type(self) -> None:
        assert NodeLabel.TYPE == "Type"

    def test_module(self) -> None:
        assert NodeLabel.MODULE == "Module"

    def test_route(self) -> None:
        assert NodeLabel.ROUTE == "Route"

    def test_service(self) -> None:
        assert NodeLabel.SERVICE == "Service"

    def test_store(self) -> None:
        assert NodeLabel.STORE == "Store"

    def test_is_str_subclass(self) -> None:
        # NodeLabel(str, Enum) — usable directly as Cypher label strings
        assert isinstance(NodeLabel.FILE, str)
        assert f"MERGE (n:{NodeLabel.FILE})" == "MERGE (n:File)"


# ---------------------------------------------------------------------------
# RelType
# ---------------------------------------------------------------------------


class TestRelType:
    def test_member_count(self) -> None:
        assert len(RelType) == 8

    def test_imports(self) -> None:
        assert RelType.IMPORTS == "IMPORTS"
        assert RelType.IMPORTS.value == "IMPORTS"

    def test_defines(self) -> None:
        assert RelType.DEFINES == "DEFINES"

    def test_calls(self) -> None:
        assert RelType.CALLS == "CALLS"

    def test_exports(self) -> None:
        assert RelType.EXPORTS == "EXPORTS"

    def test_uses_hook(self) -> None:
        assert RelType.USES_HOOK == "USES_HOOK"

    def test_has_route(self) -> None:
        assert RelType.HAS_ROUTE == "HAS_ROUTE"

    def test_has_store(self) -> None:
        assert RelType.HAS_STORE == "HAS_STORE"

    def test_belongs_to(self) -> None:
        assert RelType.BELONGS_TO == "BELONGS_TO"

    def test_is_str_subclass(self) -> None:
        assert isinstance(RelType.CALLS, str)
        assert f"-[:{RelType.CALLS}]->" == "-[:CALLS]->"


# ---------------------------------------------------------------------------
# CONSTRAINT_QUERIES
# ---------------------------------------------------------------------------


class TestConstraintQueries:
    def test_count(self) -> None:
        assert len(CONSTRAINT_QUERIES) == 7

    def test_all_contain_if_not_exists(self) -> None:
        for q in CONSTRAINT_QUERIES:
            assert "IF NOT EXISTS" in q, f"Missing IF NOT EXISTS in: {q!r}"

    def test_all_contain_is_unique(self) -> None:
        for q in CONSTRAINT_QUERIES:
            assert "IS UNIQUE" in q, f"Missing IS UNIQUE in: {q!r}"

    def test_all_are_create_constraint(self) -> None:
        for q in CONSTRAINT_QUERIES:
            assert q.strip().upper().startswith("CREATE CONSTRAINT"), (
                f"Not a CREATE CONSTRAINT statement: {q!r}"
            )

    @pytest.mark.parametrize(
        "label",
        ["File", "Function", "Component", "Hook", "Module", "Route", "Store"],
    )
    def test_covered_labels(self, label: str) -> None:
        """Each constrained node label appears in at least one query."""
        assert any(label in q for q in CONSTRAINT_QUERIES), (
            f"No constraint found for label: {label}"
        )

    def test_type_and_service_not_constrained(self) -> None:
        # Intentional: no natural unique key defined for Type or Service.
        assert not any(":Type)" in q for q in CONSTRAINT_QUERIES)
        assert not any(":Service)" in q for q in CONSTRAINT_QUERIES)

    def test_named_constraints(self) -> None:
        """All constraints use the aica_ prefix for reliable idempotency."""
        for q in CONSTRAINT_QUERIES:
            assert "aica_" in q, f"Expected named constraint with 'aica_' prefix: {q!r}"

    def test_file_path_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":File)" in q]
        assert len(match) == 1
        assert "n.path" in match[0]

    def test_function_id_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":Function)" in q]
        assert len(match) == 1
        assert "n.id" in match[0]

    def test_component_id_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":Component)" in q]
        assert len(match) == 1
        assert "n.id" in match[0]

    def test_hook_name_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":Hook)" in q]
        assert len(match) == 1
        assert "n.name" in match[0]

    def test_module_name_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":Module)" in q]
        assert len(match) == 1
        assert "n.name" in match[0]

    def test_route_route_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":Route)" in q]
        assert len(match) == 1
        assert "n.route" in match[0]

    def test_store_store_unique(self) -> None:
        match = [q for q in CONSTRAINT_QUERIES if ":Store)" in q]
        assert len(match) == 1
        assert "n.store" in match[0]


# ---------------------------------------------------------------------------
# setup_schema
# ---------------------------------------------------------------------------


class TestSetupSchema:
    def test_calls_run_query_for_each_constraint(self) -> None:
        client = MagicMock()
        setup_schema(client)
        assert client.run_query.call_count == len(CONSTRAINT_QUERIES)

    def test_passes_empty_params(self) -> None:
        """DDL statements never take parameters; empty dict must always be passed."""
        client = MagicMock()
        setup_schema(client)
        for actual_call in client.run_query.call_args_list:
            _, kwargs = actual_call
            positional_params = (
                actual_call.args[1] if len(actual_call.args) > 1 else kwargs.get("params", {})
            )
            assert positional_params == {}, (
                f"Expected empty params dict, got: {positional_params!r}"
            )

    def test_all_constraint_queries_submitted(self) -> None:
        client = MagicMock()
        setup_schema(client)
        submitted = [c.args[0] for c in client.run_query.call_args_list]
        assert submitted == CONSTRAINT_QUERIES

    def test_queries_submitted_in_order(self) -> None:
        client = MagicMock()
        setup_schema(client)
        expected_calls = [call(q, {}) for q in CONSTRAINT_QUERIES]
        client.run_query.assert_has_calls(expected_calls, any_order=False)

    def test_stops_on_run_query_exception(self) -> None:
        """If run_query raises, setup_schema propagates immediately (no silent swallow)."""
        client = MagicMock()
        client.run_query.side_effect = RuntimeError("neo4j down")
        with pytest.raises(RuntimeError, match="neo4j down"):
            setup_schema(client)
        # Only the first call was made before the exception
        assert client.run_query.call_count == 1
