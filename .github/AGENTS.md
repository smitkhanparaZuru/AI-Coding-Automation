# AICA Custom Agents

**Maintenance note (2026-03-27):** This is the concise quick-reference mirror. Keep agent names, capabilities, and examples synchronized with `../AGENTS.md` (the detailed reference).

This directory contains specialized AI agents for working with the AICA codebase. Each agent has focused expertise and constrained capabilities to ensure high-quality, consistent output.

## Available Agents

### 🔍 @aica-explorer

**Read-only codebase exploration and research**

- **Use when**: Understanding architecture, researching patterns, mapping dependencies, exploring code without changes
- **Tools**: `read`, `search` (no editing or execution)
- **Expertise**: AICA module structure, design patterns, component relationships
- **Output**: Architecture summaries, pattern documentation, research reports

**Example prompts**:

```
@aica-explorer How do detectors integrate with the scanner?
@aica-explorer Explain the LLM provider factory pattern
@aica-explorer Map the Neo4j graph schema and relationships
@aica-explorer What patterns do existing detectors follow?
```

---

### 🔧 @detector-specialist

**Creating and modifying repository scanner detectors**

- **Use when**: Adding new detectors, fixing detector bugs, extending scanner capabilities
- **Tools**: `read`, `search`, `edit` (no terminal)
- **Expertise**: Detector pattern, scanner integration, Next.js feature detection
- **Output**: Production-ready detector implementations with tests

**Example prompts**:

```
@detector-specialist Create a detector for Next.js middleware files
@detector-specialist Add API endpoint detection to the routes detector
@detector-specialist Fix the component detector to handle server components
@detector-specialist Create a detector for Next.js configuration files
```

**What it will deliver**:

- Detector file in `aica/repo_intelligence/scanner/detectors/{name}.py`
- Integration in `aica/repo_intelligence/scanner/core.py`
- Test file in `tests/test_{name}_detector.py`
- Example usage and data structure documentation

---

### ⚡ @llm-provider-specialist

**Adding and maintaining LLM provider integrations**

- **Use when**: Adding new LLM backends, implementing provider interface, fixing provider bugs
- **Tools**: `read`, `search`, `edit` (no terminal)
- **Expertise**: `BaseLLMProvider` interface, async/sync/streaming, retry logic, authentication
- **Output**: Production-ready provider implementations with tests

**Example prompts**:

```
@llm-provider-specialist Add support for Anthropic Claude API
@llm-provider-specialist Create a provider for Google Gemini
@llm-provider-specialist Fix streaming in the OpenRouter provider
@llm-provider-specialist Add support for Azure OpenAI endpoints
```

**What it will deliver**:

- Provider file in `aica/core/llm/{name}.py`
- Registration in `aica/core/llm/factory.py`
- Settings in `aica/config/settings.py`
- Test file in `tests/test_{name}_provider.py`
- Environment variable documentation

---

## Agent Selection Guide

### When to use specialized agents:

| Task                   | Agent                      | Why                               |
| ---------------------- | -------------------------- | --------------------------------- |
| Research code patterns | `@aica-explorer`           | Read-only, safe exploration       |
| Add new detector       | `@detector-specialist`     | Knows detector pattern intimately |
| Add LLM backend        | `@llm-provider-specialist` | Understands provider interface    |
| Modify existing code   | Default agent              | Full flexibility needed           |
| Run tests              | Default agent              | Needs terminal access             |
| Fix bugs               | Default agent              | May need debugging tools          |

### When to use the default agent:

- Writing or modifying tests
- Running CLI commands
- Debugging with terminal
- Multi-module refactoring

---

## Workflow Skills

AICA provides specialized workflow skills (invoked with `/skill-name`) for step-by-step guidance:

| Skill                     | Purpose                               | When to Use                               |
| ------------------------- | ------------------------------------- | ----------------------------------------- |
| `/detector-workflow`      | Complete detector development process | Learning detector pattern, need checklist |
| `/llm-provider-testing`   | Testing LLM provider implementations  | Validating providers, debugging streams   |
| `/graph-schema-extension` | Extending Neo4j graph schema          | Adding nodes/relationships to graph       |
| `/pre-release-checklist`  | Quality validation before commit/PR   | Before committing, pre-merge checks       |
| `/ast-extractor-workflow` | Creating AST code extractors          | Parsing TypeScript/JS patterns            |
| `/vector-store-workflow`  | Vector embeddings & semantic search   | Setting up embeddings, Qdrant, chunking   |

**Recommended workflow:**

1. **Learn** with skill: `/detector-workflow` (understand process)
2. **Implement** with agent: `@detector-specialist` (build feature)
3. **Validate** with skill: `/pre-release-checklist` (ensure quality)

For detailed skill documentation, see [skills/README.md](skills/README.md).

- Documentation updates
- Configuration changes
- Anything outside specialist domains

## Best Practices

### 1. Start with @aica-explorer

Before making changes, research with `@aica-explorer`:

```
@aica-explorer How do existing detectors handle missing files?
[Review findings]
@detector-specialist Create a new detector following those patterns
```

### 2. Use agents for their specialty

Don't ask `@detector-specialist` to:

- Add LLM providers (use `@llm-provider-specialist`)
- Just research code (use `@aica-explorer`)
- Run tests (use default agent)

### 3. Provide context

Give agents the information they need:

```
❌ @detector-specialist Create a detector
✅ @detector-specialist Create a detector for Next.js API routes that
   extracts endpoint paths, HTTP methods, and middleware usage
```

### 4. Iterate on output

Agents can refine their work:

```
@detector-specialist [initial implementation]
User: Add support for dynamic route segments
@detector-specialist [updated implementation]
```

## Agent Capabilities Matrix

| Capability   | @aica-explorer | @detector-specialist | @llm-provider-specialist | Default |
| ------------ | :------------: | :------------------: | :----------------------: | :-----: |
| Read files   |       ✅       |          ✅          |            ✅            |   ✅    |
| Search code  |       ✅       |          ✅          |            ✅            |   ✅    |
| Edit files   |       ❌       |          ✅          |            ✅            |   ✅    |
| Run commands |       ❌       |          ❌          |            ❌            |   ✅    |
| Create tests |       ❌       |          ✅          |            ✅            |   ✅    |
| Run tests    |       ❌       |          ❌          |            ❌            |   ✅    |

## Workflow Examples

### Adding a New Detector

```bash
# 1. Research existing patterns
@aica-explorer What patterns do route and component detectors follow?

# 2. Create the detector
@detector-specialist Create a detector for Next.js middleware that extracts
matcher patterns and execution order

# 3. Run tests (default agent)
Run the new detector tests and fix any issues
```

### Adding a New LLM Provider

```bash
# 1. Research the provider interface
@aica-explorer Explain the BaseLLMProvider interface and show implementation examples

# 2. Create the provider
@llm-provider-specialist Add support for Anthropic Claude API with streaming

# 3. Test integration (default agent)
Test the new provider with a sample prompt and verify streaming works
```

### Understanding a Module

```bash
# Pure research - no changes needed
@aica-explorer How does the Neo4j graph store work? Show the schema,
node types, relationship types, and how the graph is built from AST data
```

## Tips

### Getting Better Results

1. **Be specific**: Include detailed requirements
2. **Provide examples**: Reference existing code to emulate
3. **State constraints**: Mention edge cases to handle
4. **Request tests**: Always ask for test coverage

### Common Mistakes

❌ Using `@detector-specialist` for LLM work
❌ Asking `@aica-explorer` to make changes
❌ Not providing enough context about requirements
❌ Forgetting to test the output

## Extending This System

To add a new specialized agent:

1. Create `{name}.agent.md` in this directory
2. Define clear scope in `description:` (for auto-discovery)
3. Limit `tools:` to minimal necessary set
4. Document the agent in this AGENTS.md file
5. Add workflow examples

Common agent patterns:

- **Read-only researcher**: `tools: [read, search]`
- **Safe editor**: `tools: [read, search, edit]` (no terminal)
- **Test runner**: `tools: [read, search, edit, execute]`

---

## Questions?

- See `.github/copilot-instructions.md` for AICA coding guidelines
- See individual `.agent.md` files for agent implementation details
- See VS Code Copilot documentation for agent customization
