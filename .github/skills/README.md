# AICA Skills Directory

This directory contains specialized workflow skills for the AICA project. Each skill provides step-by-step guidance for common development tasks.

## Available Skills

### 1. 🔧 detector-workflow

**Complete workflow for creating repository scanner detectors**

- 8-step process from planning to integration
- Common detection patterns reference guide
- Quality checklist with 12+ validation points
- Complements `@detector-specialist` agent

**Invoke:** `/detector-workflow Create a detector for middleware files`

**Use when:**

- Adding new detector for Next.js features
- Implementing detection logic
- Integrating with scanner
- Following AICA detector conventions

---

### 2. 🧪 llm-provider-testing

**Structured testing workflow for LLM provider integrations**

- Unit tests for all four required methods (sync/async, generate/stream)
- Error handling tests (auth, connection, timeout)
- Retry logic validation
- Integration and performance testing
- Security validation (no leaked secrets)

**Invoke:** `/llm-provider-testing Validate OpenRouter streaming`

**Use when:**

- Testing new LLM provider implementation
- Validating sync/async/streaming capabilities
- Debugging provider issues
- Ensuring retry logic works

---

### 3. 📊 graph-schema-extension

**Workflow for extending Neo4j graph schema**

- Add new node and relationship types
- Create node builder methods
- Integrate with graph builder
- Write Cypher queries
- Performance optimization tips

**Invoke:** `/graph-schema-extension Add middleware nodes and relationships`

**Use when:**

- Adding new node types to knowledge graph
- Creating relationships between nodes
- Integrating scanner data into graph
- Building graph analysis queries

---

### 4. 🔄 sync-workflow

**Complete workflow for incremental repository synchronization**

- Change detection via git + content hashing
- Incremental vs full mode decision logic
- Scanner, AST, Graph, Embeddings sync pipeline
- Fallback threshold configuration
- CI/CD integration patterns
- Troubleshooting sync issues

**Invoke:** `/sync-workflow Configure fallback threshold`

**Use when:**

- Syncing code changes incrementally
- Understanding incremental vs full rebuild modes
- Configuring sync behavior for your project
- Integrating AICA into development workflow
- Setting up CI/CD pipelines with sync
- Troubleshooting "no changes detected" errors

---

### 5. ✅ pre-release-checklist

**Quality gates before committing or releasing**

- Comprehensive validation checklist (tests, lint, types, coverage)
- Security checks (no secrets, safe logging)
- Documentation validation
- Feature-specific checklists
- Automated pre-commit hook template

**Invoke:** `/pre-release-checklist Validate before commit`

**Use when:**

- Before committing changes
- Before creating pull request
- Pre-merge validation
- Ensuring code quality standards

---

### 6. 🌳 ast-extractor-workflow

**Workflow for creating AST extractors**

- Parse TypeScript/JavaScript with tree-sitter
- Extract imports, exports, functions, types, patterns
- Implement custom AST visitors
- Common extraction patterns library
- Integration with AST runner

**Invoke:** `/ast-extractor-workflow Create extractor for React hooks`

**Use when:**

- Adding new AST extractor
- Parsing code patterns
- Extracting metadata from source
- Analyzing code structure

---

### 7. 🔍 vector-store-workflow

**Complete workflow for vector embeddings and semantic search**

- Embedding provider setup (Ollama vs OpenRouter)
- Qdrant vector database configuration
- Code chunking strategies (functions, components, types)
- Semantic search with filters and re-ranking
- Incremental embedding updates
- CLI commands reference

**Invoke:** `/vector-store-workflow Set up Ollama embeddings`

**Use when:**

- Setting up embeddings and semantic search
- Configuring Qdrant vector database
- Implementing custom chunking strategies
- Building semantic code search queries
- Testing vector search functionality
- Incremental embedding updates for changed files

---

## Skill vs Agent Decision Guide

| Need                  | Use                                  |
| --------------------- | ------------------------------------ |
| Learn the process     | Skill (e.g., `/detector-workflow`)   |
| Implement the feature | Agent (e.g., `@detector-specialist`) |
| Quick reference       | Skill                                |
| Quality validation    | `/pre-release-checklist` skill       |
| Testing guidance      | `/llm-provider-testing` skill        |

**Typical workflow:**

1. Read the skill to understand the process
2. Invoke the specialist agent to implement
3. Use pre-release-checklist before committing

## Skill Structure

Each skill follows this structure:

```
.github/skills/<skill-name>/
├── SKILL.md              # Main workflow guide
├── references/           # Additional reference materials
│   └── *.md
└── README.md            # Usage guide (optional)
```

## How Skills Work

Skills are **progressive loading** - VS Code Copilot loads only what's needed:

1. **Discovery** (~100 tokens): Reads skill name and description
2. **Instructions** (<5000 tokens): Loads SKILL.md body when invoked
3. **Resources**: Reference files loaded only when mentioned

## Invoking Skills

### As Slash Commands

Type `/` in Copilot Chat to see all available skills:

```
/detector-workflow Create middleware detector
/pre-release-checklist Validate changes
/graph-schema-extension Add new node type
```

### In Conversation

Mention the skill naturally:

```
I need to add a new detector. Can you help with the detector-workflow?
Before I commit, let's run through the pre-release-checklist
```

### Model Auto-Invocation

Skills are automatically loaded when relevant to your question:

```
User: "How do I create a new detector?"
→ Copilot auto-loads detector-workflow skill
```

## Creating New Skills

To add a new skill:

1. Create directory: `.github/skills/<skill-name>/`
2. Create `SKILL.md` with YAML frontmatter and workflow steps
3. Add reference materials in `references/` (optional)
4. Test by typing `/skill-name` in Copilot Chat

**See:** [agent-customization skill](https://code.visualstudio.com/docs/copilot/customization) for templates and guidelines

## Maintenance

### Updating Skills

When AICA conventions change:

- Update relevant SKILL.md files
- Update reference materials
- Test with real examples
- Update this README

### Deprecating Skills

If a skill becomes obsolete:

1. Add `user-invocable: false` to frontmatter
2. Document deprecation reason in skill
3. Point to replacement skill/agent

## Related Resources

- [Custom Agents](../AGENTS.md) - Specialized implementation agents
- [Coding Guidelines](../copilot-instructions.md) - AICA conventions
- [Contributing Guide](../../CONTRIBUTING.md)
- [Documentation](../../docs/)

---

**Need help?** Use the VS Code agent customization docs to create or modify skills:
https://code.visualstudio.com/docs/copilot/customization/customization-overview
