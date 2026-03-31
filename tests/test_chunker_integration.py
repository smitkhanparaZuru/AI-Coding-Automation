"""
Integration tests for aica.memory.vector_store.chunkers

Tests full chunking workflow on realistic repository structures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aica.memory.vector_store.chunkers import create_code_chunks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def realistic_repo(tmp_path: Path) -> Path:
    """Create a realistic minimal repository structure with AST outputs."""
    # Create directory structure
    src = tmp_path / "src"
    features = src / "features"
    auth = features / "Auth"
    components = src / "components"
    types = src / "types"

    for dir_path in [auth, components, types]:
        dir_path.mkdir(parents=True)

    # Create source files
    (auth / "login.ts").write_text(
        """import { validateEmail } from '@/utils/validation';

/**
 * Authenticate user with credentials
 */
export async function authenticateUser(email: string, password: string) {
  if (!validateEmail(email)) {
    throw new Error('Invalid email');
  }
  
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  
  return response.json();
}

export function logout() {
  localStorage.removeItem('token');
}
""",
        encoding="utf-8",
    )

    (components / "LoginForm.tsx").write_text(
        """import React, { useState } from 'react';
import { authenticateUser } from '@/features/Auth/login';

/**
 * Login form component
 */
export function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await authenticateUser(email, password);
    onSuccess();
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <input value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button type="submit">Login</button>
    </form>
  );
}
""",
        encoding="utf-8",
    )

    (types / "user.ts").write_text(
        """/**
 * User entity type
 */
export interface User {
  id: string;
  email: string;
  role: 'admin' | 'user';
  createdAt: Date;
}

export interface LoginFormProps {
  onSuccess: () => void;
}

export type AuthStatus = 'authenticated' | 'unauthenticated' | 'loading';
""",
        encoding="utf-8",
    )

    # Create AST outputs
    ast_dir = tmp_path / ".repo_intelligence" / "ast"
    ast_dir.mkdir(parents=True)

    functions = [
        {
            "file": "src/features/Auth/login.ts",
            "name": "authenticateUser",
            "kind": "function",
            "async": True,
            "params": ["email", "password"],
            "line": 6,
            "exported": True,
        },
        {
            "file": "src/features/Auth/login.ts",
            "name": "logout",
            "kind": "function",
            "async": False,
            "params": [],
            "line": 21,
            "exported": True,
        },
        {
            "file": "src/components/LoginForm.tsx",
            "name": "handleSubmit",
            "kind": "arrow",
            "async": True,
            "params": ["e"],
            "line": 11,
            "exported": False,
        },
    ]

    components = [
        {
            "file": "src/components/LoginForm.tsx",
            "name": "LoginForm",
            "kind": "function",
            "props": ["onSuccess"],
            "line": 7,
            "exported": True,
        }
    ]

    types = [
        {
            "file": "src/types/user.ts",
            "name": "User",
            "kind": "interface",
            "members": ["id", "email", "role", "createdAt"],
            "line": 4,
            "exported": True,
        },
        {
            "file": "src/types/user.ts",
            "name": "LoginFormProps",
            "kind": "interface",
            "members": ["onSuccess"],
            "line": 11,
            "exported": True,
        },
        {
            "file": "src/types/user.ts",
            "name": "AuthStatus",
            "kind": "type",
            "members": [],
            "line": 15,
            "exported": True,
        },
    ]

    imports = [
        {
            "file": "src/features/Auth/login.ts",
            "source": "@/utils/validation",
            "import_kind": "alias",
            "default": None,
            "named": [{"name": "validateEmail", "alias": None}],
            "line": 1,
        },
        {
            "file": "src/components/LoginForm.tsx",
            "source": "react",
            "import_kind": "external",
            "default": "React",
            "named": [{"name": "useState", "alias": None}],
            "line": 1,
        },
        {
            "file": "src/components/LoginForm.tsx",
            "source": "@/features/Auth/login",
            "import_kind": "alias",
            "default": None,
            "named": [{"name": "authenticateUser", "alias": None}],
            "line": 2,
        },
    ]

    (ast_dir / "functions.json").write_text(json.dumps(functions), encoding="utf-8")
    (ast_dir / "components.json").write_text(json.dumps(components), encoding="utf-8")
    (ast_dir / "types.json").write_text(json.dumps(types), encoding="utf-8")
    (ast_dir / "imports.json").write_text(json.dumps(imports), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_create_code_chunks_on_realistic_repo(self, realistic_repo: Path):
        """Process realistic repo structure with full workflow."""
        chunks = create_code_chunks(realistic_repo)

        # Verify chunk count
        # 3 functions + 1 component + 3 types = 7 chunks
        assert len(chunks) >= 6  # Allow for some internal entities

        # Verify all chunk types present
        chunk_types = {c.metadata.chunk_type for c in chunks}
        assert "function" in chunk_types
        assert "component" in chunk_types
        assert "type" in chunk_types

        # Verify IDs are unique
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

        # Verify all chunks have text
        assert all(c.text for c in chunks)

        # Verify all chunks have complete metadata
        for chunk in chunks:
            assert chunk.metadata.file
            assert chunk.metadata.line > 0
            assert chunk.metadata.name
            assert chunk.metadata.chunk_type in ("function", "component", "type")

    def test_feature_detection_works(self, realistic_repo: Path):
        """Verify feature names are extracted from directory structure."""
        chunks = create_code_chunks(realistic_repo)

        # Find Auth feature chunks
        auth_chunks = [c for c in chunks if "Auth" in c.metadata.file]

        # Should detect "Auth" feature
        auth_features = [c.metadata.feature for c in auth_chunks if c.metadata.feature]
        assert any("Auth" in f for f in auth_features if f)

    def test_dependency_enrichment_works(self, realistic_repo: Path):
        """Verify dependencies are populated from imports.json."""
        chunks = create_code_chunks(realistic_repo)

        # Find LoginForm component
        login_form = [c for c in chunks if c.metadata.name == "LoginForm"]
        assert len(login_form) == 1

        # Should have dependencies
        deps = login_form[0].metadata.dependencies
        assert len(deps) > 0
        assert "react" in deps
        assert "@/features/Auth/login" in deps

    def test_chunk_text_contains_source_code(self, realistic_repo: Path):
        """Verify exported text contains actual source code."""
        chunks = create_code_chunks(realistic_repo)

        # Find authenticateUser function
        auth_fn = [c for c in chunks if c.metadata.name == "authenticateUser"]
        assert len(auth_fn) == 1

        text = auth_fn[0].text

        # Should contain function signature and body
        assert "authenticateUser" in text
        assert "email" in text
        assert "password" in text
        assert "fetch" in text or "validateEmail" in text

    def test_metadata_accuracy(self, realistic_repo: Path):
        """Verify metadata fields match source data."""
        chunks = create_code_chunks(realistic_repo)

        # Find User interface
        user_type = [c for c in chunks if c.metadata.name == "User"]
        assert len(user_type) == 1

        metadata = user_type[0].metadata

        # Verify fields
        assert metadata.file == "src/types/user.ts"
        assert metadata.chunk_type == "type"
        assert metadata.kind == "interface"
        assert metadata.exported is True
        assert set(metadata.members) == {"id", "email", "role", "createdAt"}

    def test_language_detection_correct(self, realistic_repo: Path):
        """Verify language is correctly detected from file extensions."""
        chunks = create_code_chunks(realistic_repo)

        # TypeScript files
        ts_chunks = [c for c in chunks if c.metadata.file.endswith(".ts")]
        assert all(c.metadata.language == "typescript" for c in ts_chunks)

        # TSX files
        tsx_chunks = [c for c in chunks if c.metadata.file.endswith(".tsx")]
        assert all(c.metadata.language == "tsx" for c in tsx_chunks)

    def test_exported_entities_captured(self, realistic_repo: Path):
        """Verify exported entities are marked as exported."""
        chunks = create_code_chunks(realistic_repo)

        # Find exported entities
        exported = [c for c in chunks if c.metadata.exported]

        # Should have multiple exported entities
        assert len(exported) >= 5

        # Verify names
        exported_names = {c.metadata.name for c in exported}
        assert "authenticateUser" in exported_names
        assert "LoginForm" in exported_names
        assert "User" in exported_names

    def test_chunk_count_within_expected_range(self, realistic_repo: Path):
        """Verify chunk count is reasonable for repo size."""
        chunks = create_code_chunks(realistic_repo)

        # Realistic fixture should produce 6-10 chunks
        assert 6 <= len(chunks) <= 10


# ---------------------------------------------------------------------------
# Optional: Real repository test (requires ZURU GPT repo)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Requires actual ZURU GPT repository")
def test_on_zuru_gpt_repo():
    """Test on actual ZURU GPT repository (manual verification).

    To run manually:
        pytest tests/test_chunker_integration.py::test_on_zuru_gpt_repo -v -s

    Expected:
        - 800-1500 chunks for typical Next.js app
        - All chunks have complete metadata
        - No exceptions raised
    """
    from pathlib import Path

    # Adjust path as needed
    zuru_gpt_path = Path("/path/to/zuru-gpt")

    if not zuru_gpt_path.exists():
        pytest.skip("ZURU GPT repository not found")

    chunks = create_code_chunks(zuru_gpt_path)

    print(f"\n=== ZURU GPT Chunking Results ===")
    print(f"Total chunks: {len(chunks)}")

    # Group by type
    by_type = {}
    for chunk in chunks:
        typ = chunk.metadata.chunk_type
        by_type[typ] = by_type.get(typ, 0) + 1

    for typ, count in sorted(by_type.items()):
        print(f"  {typ}: {count}")

    # Sample 5 random chunks
    import random

    sample = random.sample(chunks, min(5, len(chunks)))
    print("\n=== Sample Chunks ===")
    for chunk in sample:
        print(f"\nID: {chunk.id}")
        print(f"Type: {chunk.metadata.chunk_type}")
        print(f"File: {chunk.metadata.file}")
        print(f"Exported: {chunk.metadata.exported}")
        print(f"Feature: {chunk.metadata.feature}")
        print(f"Text preview: {chunk.text[:100]}...")

    # Assertions
    assert 800 <= len(chunks) <= 2000, f"Unexpected chunk count: {len(chunks)}"
    assert all(c.text for c in chunks), "Some chunks have empty text"
    assert all(c.metadata.file for c in chunks), "Some chunks missing file metadata"
