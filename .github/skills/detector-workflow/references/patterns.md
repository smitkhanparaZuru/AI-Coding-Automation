# Common Detector Patterns

Reference guide for implementing specific detection scenarios in AICA detectors.

## File Globbing Patterns

### Recursive Search with Multiple Extensions

```python
patterns = ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
for pattern in patterns:
    for file_path in repo_path.rglob(pattern):
        # Process file
        pass
```

### Directory-Specific Search

```python
# Search only in specific directory
app_dir = repo_path / "app"
if app_dir.exists():
    for file_path in app_dir.rglob("*.tsx"):
        # Process file
        pass
```

### Exact File Names

```python
# Find all middleware.ts files
for file_path in repo_path.rglob("middleware.ts"):
    # Process file
    pass
```

## Path Handling

### Relative Paths (Required for Output)

```python
# Convert absolute to relative
rel_path = str(file_path.relative_to(repo_path))
```

### Route Extraction from File Path

```python
# For app/dashboard/settings/page.tsx -> /dashboard/settings
app_dir = repo_path / "app"
route = "/" + str(file_path.parent.relative_to(app_dir))
```

### Parent Directory Name

```python
# Get immediate parent folder name
folder_name = file_path.parent.name
```

## File Content Parsing

### Read File with Error Handling

```python
try:
    content = file_path.read_text(encoding="utf-8")
except Exception as e:
    log.warning("file.read_failed", path=str(file_path), error=str(e))
    continue
```

### Check for Patterns in Content

```python
content = file_path.read_text(encoding="utf-8")

# Check for exports
has_default_export = "export default" in content
has_named_exports = "export const" in content or "export function" in content

# Check for specific imports
uses_server = "'use server'" in content or '"use server"' in content
uses_client = "'use client'" in content or '"use client"' in content
```

### Extract Specific Lines

```python
lines = content.split("\n")
for line in lines:
    if line.startswith("export"):
        # Process export line
        pass
```

## JSON/Configuration File Parsing

### Parse package.json

```python
import json

package_json_path = repo_path / "package.json"
if package_json_path.exists():
    try:
        data = json.loads(package_json_path.read_text(encoding="utf-8"))
        dependencies = data.get("dependencies", {})
        scripts = data.get("scripts", {})
    except json.JSONDecodeError as e:
        log.warning("json.parse_failed", path="package.json", error=str(e))
```

### Parse next.config.js (as text)

```python
config_path = repo_path / "next.config.js"
if config_path.exists():
    content = config_path.read_text(encoding="utf-8")
    # Simple text-based detection
    has_app_dir = "appDir: true" in content
```

## Common Metadata Structures

### Route Detection

```python
{
    "path": "app/dashboard/page.tsx",
    "route": "/dashboard",
    "type": "page",
    "is_dynamic": False,
    "is_layout": False,
    "segments": ["dashboard"]
}
```

### Component Detection

```python
{
    "path": "components/Button.tsx",
    "name": "Button",
    "type": "client",  # "server" | "client" | "shared"
    "exports": ["Button", "ButtonProps"],
    "has_default_export": True
}
```

### Hook Detection

```python
{
    "path": "hooks/useAuth.ts",
    "name": "useAuth",
    "type": "custom_hook",
    "dependencies": ["react", "next-auth"]
}
```

### Service/API Detection

```python
{
    "path": "lib/api/users.ts",
    "name": "users",
    "exports": ["getUser", "createUser", "updateUser"],
    "type": "api_service"
}
```

## Logging Patterns

### Standard Detection Lifecycle

```python
def detect(self, repo_path: Path) -> list[dict]:
    log.info("detection.started", path=str(repo_path))

    results = []
    # Detection logic

    log.debug("detection.completed", count=len(results))
    return results
```

### Warning for Missing Expected Files

```python
expected_dir = repo_path / "app"
if not expected_dir.exists():
    log.warning("directory.not_found", path="app", detector=self.__class__.__name__)
    return []
```

### Debug Information During Scan

```python
log.debug("files.found", pattern="**/*.tsx", count=len(files))
```

## Conditional Detection

### Framework Version Detection

```python
def detect(self, repo_path: Path) -> list[dict]:
    # Check if using App Router
    app_dir = repo_path / "app"
    pages_dir = repo_path / "pages"

    if app_dir.exists():
        return self._detect_app_router(repo_path, app_dir)
    elif pages_dir.exists():
        return self._detect_pages_router(repo_path, pages_dir)
    else:
        log.warning("no_router_found", path=str(repo_path))
        return []
```

### Feature-Based Detection

```python
# Only detect if feature is enabled
package_json = repo_path / "package.json"
if package_json.exists():
    data = json.loads(package_json.read_text(encoding="utf-8"))
    if "next-auth" in data.get("dependencies", {}):
        # Proceed with auth detection
        pass
```

## Performance Optimization

### Limit Recursion Depth

```python
# Don't search in node_modules or .next
for file_path in repo_path.rglob("*.tsx"):
    if "node_modules" in file_path.parts or ".next" in file_path.parts:
        continue
    # Process file
```

### Early Exit

```python
# Stop after finding singleton
config_locations = ["next.config.js", "next.config.mjs", "next.config.ts"]
for config_file in config_locations:
    config_path = repo_path / config_file
    if config_path.exists():
        return {"path": config_file, "type": "next_config"}
return {}  # Not found
```

### Batch Processing

```python
# Collect all files first, then process
files = list(repo_path.rglob("*.tsx"))
log.debug("files.collected", count=len(files))

for file_path in files:
    # Process each file
    pass
```

## Testing Patterns

### Create Test Files in tmp_path

```python
def test_detector_finds_items(tmp_path: Path) -> None:
    # Create directory structure
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    # Create test file
    (app_dir / "page.tsx").write_text("export default function Page() {}")

    # Run detector
    detector = MyDetector()
    result = detector.detect(tmp_path)

    # Assertions
    assert len(result) == 1
    assert result[0]["path"] == "app/page.tsx"
```

### Test Multiple Scenarios

```python
@pytest.mark.parametrize("filename,expected_type", [
    ("page.tsx", "page"),
    ("layout.tsx", "layout"),
    ("loading.tsx", "loading"),
])
def test_detector_identifies_types(tmp_path: Path, filename: str, expected_type: str) -> None:
    (tmp_path / filename).write_text("export default function() {}")

    detector = MyDetector()
    result = detector.detect(tmp_path)

    assert result[0]["type"] == expected_type
```

## Error Handling

### Graceful Degradation

```python
try:
    content = file_path.read_text(encoding="utf-8")
except UnicodeDecodeError:
    # Try with different encoding
    try:
        content = file_path.read_text(encoding="latin-1")
    except Exception as e:
        log.warning("file.encoding_failed", path=str(file_path), error=str(e))
        continue
except Exception as e:
    log.error("file.read_error", path=str(file_path), error=str(e))
    continue
```

### Validation

```python
def _validate_result(self, result: dict) -> bool:
    """Validate result has required fields."""
    required_fields = ["path", "type"]
    for field in required_fields:
        if field not in result:
            log.warning("result.missing_field", field=field, result=result)
            return False
    return True
```

## Complete Example: Simple Middleware Detector

```python
"""Detector for Next.js middleware files."""

from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("detector.middleware")


class MiddlewareDetector:
    """Detect Next.js middleware files.

    Returns:
        list[dict]: List of detected middleware files.
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Scan repo_path for middleware files.

        Args:
            repo_path: Absolute path to repository root.

        Returns:
            List of middleware metadata dicts.
        """
        log.info("detection.started", path=str(repo_path))

        results = []

        # Find all middleware.ts/js files
        for pattern in ["**/middleware.ts", "**/middleware.js"]:
            for file_path in repo_path.rglob(pattern.split("**/")[1]):
                # Skip node_modules
                if "node_modules" in file_path.parts:
                    continue

                rel_path = str(file_path.relative_to(repo_path))

                # Determine scope
                scope = "global" if file_path.parent == repo_path else "route"

                results.append({
                    "path": rel_path,
                    "scope": scope,
                    "directory": str(file_path.parent.relative_to(repo_path))
                })

        log.debug("detection.completed", count=len(results))
        return results
```
