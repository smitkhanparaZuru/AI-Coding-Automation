---
description: "Guide for using AICA's specialized custom agents effectively. Shows when to use each agent, example prompts, and workflows."
---

# Using AICA Custom Agents

Quick reference for choosing and using the right specialized agent for your task.

## Quick Decision Tree

```
Need to make changes?
├─ No → @aica-explorer (research only)
└─ Yes → What are you working on?
    ├─ Scanner detector → @detector-specialist
    ├─ LLM provider → @llm-provider-specialist
    └─ Something else → Default agent
```

## Agent Cheat Sheet

### @aica-explorer 🔍

**Read-only research**

```
@aica-explorer How does the graph store schema work?
@aica-explorer What patterns do detectors follow?
@aica-explorer Trace data flow from scanner to Neo4j
```

### @detector-specialist 🔧

**Create/modify detectors**

```
@detector-specialist Create detector for Next.js middleware
@detector-specialist Add dynamic route support to routes detector
@detector-specialist Fix component detector server component handling
```

### @llm-provider-specialist ⚡

**Add/fix LLM providers**

```
@llm-provider-specialist Add Anthropic Claude support
@llm-provider-specialist Fix streaming in OpenRouter provider
@llm-provider-specialist Add retry logic to Ollama provider
```

## Common Workflows

### Workflow 1: Adding a New Feature Detector

```bash
# Step 1: Research
@aica-explorer Show me how existing detectors handle file walking and error cases

# Step 2: Implement
@detector-specialist Create a detector for Next.js Server Actions that:
- Scans for "use server" directive
- Extracts action names and parameters
- Handles both inline and file-level directives

# Step 3: Test (default agent)
Run the new detector tests and verify output format
```

### Workflow 2: Adding an LLM Provider

```bash
# Step 1: Research
@aica-explorer Explain BaseLLMProvider interface with examples

# Step 2: Implement
@llm-provider-specialist Add Google Gemini provider with:
- Streaming support
- Proper error handling
- API key authentication

# Step 3: Integration test (default agent)
Test the Gemini provider with a sample prompt and check response
```

### Workflow 3: Understanding Complex Code

```bash
# Research only - no implementation
@aica-explorer Document the complete flow from:
1. AST extraction in repo_intelligence/ast/
2. Graph building in memory/graph_store/
3. Neo4j query patterns used

Show key classes, methods, and data structures at each stage.
```

## Tips

### ✅ Good Prompts

- **Specific**: "Create detector for API routes with HTTP method extraction"
- **Context**: "Following the pattern used in routes.py detector"
- **Complete**: "Include error handling for missing files and test coverage"

### ❌ Avoid

- **Vague**: "Make a detector"
- **Wrong agent**: Asking @detector-specialist to add LLM providers
- **No context**: Not mentioning which patterns to follow

## Agent Capabilities

| Feature      | Explorer | Detector Spec | LLM Spec | Default |
| ------------ | :------: | :-----------: | :------: | :-----: |
| Read files   |    ✅    |      ✅       |    ✅    |   ✅    |
| Edit files   |    ❌    |      ✅       |    ✅    |   ✅    |
| Run commands |    ❌    |      ❌       |    ❌    |   ✅    |
| Create tests |    ❌    |      ✅       |    ✅    |   ✅    |

## When to Use Default Agent

Use the default agent (no @mention) for:

- Running tests or CLI commands
- Multi-module refactoring
- Debugging with terminal
- Writing documentation
- Tasks outside specialist domains
- Need full tool access

## Full Documentation

See `.github/AGENTS.md` for complete agent documentation.
