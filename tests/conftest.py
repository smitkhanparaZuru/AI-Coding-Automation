from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def nextjs_repo(tmp_path: Path) -> Path:
    """Minimal Next.js 16 App Router TypeScript repo fixture."""
    # package.json with next + react
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "my-app",
                "version": "0.1.0",
                "dependencies": {
                    "next": "^16.0.0",
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0",
                },
                "devDependencies": {
                    "typescript": "^5.0.0",
                    "@types/react": "^18.0.0",
                },
            }
        ),
        encoding="utf-8",
    )

    # Lockfile — pnpm
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n", encoding="utf-8")

    # tsconfig signals TypeScript
    (tmp_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"target": "ES2022"}}),
        encoding="utf-8",
    )

    # next.config.ts
    (tmp_path / "next.config.ts").write_text("export default {};\n", encoding="utf-8")

    # App Router layout
    app_dir = tmp_path / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return null; }\n", encoding="utf-8"
    )
    (app_dir / "layout.tsx").write_text(
        "export default function Layout({ children }: any) { return children; }\n",
        encoding="utf-8",
    )

    # Common src dirs
    for dirname in ("components", "lib", "services", "hooks", "utils"):
        (tmp_path / "src" / dirname).mkdir(parents=True, exist_ok=True)

    # Drizzle config
    (tmp_path / "drizzle.config.ts").write_text("export default {};\n", encoding="utf-8")

    # Env files
    (tmp_path / ".env").write_text("DATABASE_URL=postgres://localhost/db\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("NEXTAUTH_SECRET=test\n", encoding="utf-8")

    # Tailwind
    (tmp_path / "tailwind.config.ts").write_text("export default {};\n", encoding="utf-8")

    return tmp_path
