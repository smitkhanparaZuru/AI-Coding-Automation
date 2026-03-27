# AICA Quick Reference

## 🚀 Agents (for implementation)

| Agent                      | Use Case                    | Example                                           |
| -------------------------- | --------------------------- | ------------------------------------------------- |
| `@aica-explorer`           | Research & explore codebase | `@aica-explorer How do detectors work?`           |
| `@detector-specialist`     | Build/fix detectors         | `@detector-specialist Create middleware detector` |
| `@llm-provider-specialist` | Add/fix LLM providers       | `@llm-provider-specialist Add Claude support`     |
| Default agent              | Tests, CLI, debugging       | `Run tests and show me the output`                |

## 📚 Skills (for workflow guidance)

| Skill                     | Purpose                    | Invoke                                         |
| ------------------------- | -------------------------- | ---------------------------------------------- |
| `/detector-workflow`      | Detector development steps | `/detector-workflow middleware detector`       |
| `/llm-provider-testing`   | Provider test guide        | `/llm-provider-testing validate streaming`     |
| `/graph-schema-extension` | Add graph nodes/rels       | `/graph-schema-extension add middleware nodes` |
| `/pre-release-checklist`  | Quality validation         | `/pre-release-checklist`                       |
| `/ast-extractor-workflow` | AST extraction guide       | `/ast-extractor-workflow extract hooks`        |

## 🎯 Common Workflows

### Adding a New Detector

```
1. /detector-workflow                    # Learn the process
2. @detector-specialist Create detector  # Implement
3. pytest tests/test_new_detector.py     # Test
4. /pre-release-checklist               # Validate
5. git commit                            # Commit
```

### Adding a New LLM Provider

```
1. @llm-provider-specialist Add provider
2. /llm-provider-testing                # Validate implementation
3. pytest tests/test_provider.py --cov
4. /pre-release-checklist
5. git commit
```

### Extending Graph Schema

```
1. /graph-schema-extension              # Learn the process
2. Edit schema.py, add node types
3. Create builder methods
4. pytest tests/test_builder.py
5. Test with Neo4j Browser
6. /pre-release-checklist
```

### Creating AST Extractor

```
1. /ast-extractor-workflow              # Learn the process
2. Create extractor in ast/extractors/
3. Integrate with runner.py
4. pytest tests/test_extractor.py
5. /pre-release-checklist
```

## 🔍 Quick Commands

### Testing

```bash
pytest tests/ -v                        # All tests
pytest tests/ -x                        # Stop on first failure
pytest tests/ --cov=aica --cov-report=term-missing
pytest tests/ -m integration            # Integration tests only
```

### Code Quality

```bash
ruff check aica/                        # Lint
ruff format aica/                       # Format
mypy aica/                              # Type check
```

### Development

```bash
aica scan-repo --verbose                # Scan repository
aica index-code                         # Index with AST
aica sync-repo                          # Incremental sync after local changes
aica build-graph                        # Build Neo4j graph
```

### Neo4j

```cypher
MATCH (n) RETURN n LIMIT 25            // View nodes
MATCH ()-[r]->() RETURN r LIMIT 25     // View relationships
```

## 🆘 Getting Help

| Question           | Action                          |
| ------------------ | ------------------------------- |
| How does X work?   | `@aica-explorer Explain X`      |
| How do I create Y? | `/Y-workflow` (if skill exists) |
| Can you build Z?   | `@specialist-agent Build Z`     |
| Before committing? | `/pre-release-checklist`        |

## 📖 Documentation

- [Skills Guide](skills/README.md)
- [Agents Guide](AGENTS.md)
- [Coding Guidelines](copilot-instructions.md)
- [Contributing](../CONTRIBUTING.md)
- [Full Docs](../docs/)

---

**Tip:** Type `/` in Copilot Chat to see all available skills as slash commands!
