# AICA Custom Agents

**Maintenance note (2026-03-27):** This is the detailed reference for AICA agents. Keep the agent list, capabilities, and examples synchronized with `.github/AGENTS.md` (the concise quick-reference mirror).

This document describes the custom agents available in the AICA project. These agents are specialized subagents that can be invoked to handle specific tasks within the AICA ecosystem.

## Overview

AICA uses custom agents to provide specialized expertise for different aspects of the codebase. Each agent has focused responsibilities, minimal tool access, and clear boundaries to ensure quality and consistency.

## Available Agents

### 1. AICA Explorer

**Purpose**: Read-only codebase exploration and analysis

**Location**: `.github/agents/aica-explorer.agent.md`

**When to Use**:

- Researching architecture patterns
- Understanding code flow
- Analyzing dependencies
- Exploring module structure
- Documenting patterns without making changes

**Tools**: `read`, `search` (read-only)

**Invocation**:

```
@aica-explorer Explain how the scanner detector system works
@aica-explorer Map the dependencies between the core modules
@aica-explorer What AST extractors exist and what do they extract?
```

---

### 2. Detector Specialist

**Purpose**: Create and modify AICA repository scanner detectors

**Location**: `.github/agents/detector-specialist.agent.md`

**When to Use**:

- Adding new detector for framework features
- Fixing detector bugs
- Extending scanner capabilities
- Implementing detection logic for Next.js patterns

**Tools**: `read`, `search`, `edit`

**Invocation**:

```
@detector-specialist Create a detector for Next.js middleware files
@detector-specialist Fix the routes detector to handle parallel routes
@detector-specialist Add support for detecting Server Actions
```

**Key Responsibilities**:

- Follows strict detector pattern in `aica/repo_intelligence/scanner/detectors/`
- Ensures consistency with 17 existing detectors
- Implements read-only analysis (never modifies target repos)
- Returns `list[dict]` for collections, `dict` for singletons
- Uses structured logging with `debug` package

---

### 3. LLM Provider Specialist

**Purpose**: Create and modify AICA LLM provider integrations

**Location**: `.github/agents/llm-provider-specialist.agent.md`

**When to Use**:

- Adding new LLM backend support
- Implementing provider interface
- Fixing provider bugs
- Handling streaming responses
- Implementing retry logic

**Tools**: `read`, `search`, `edit`

**Invocation**:

```
@llm-provider-specialist Add support for Anthropic Claude API
@llm-provider-specialist Fix streaming timeout in OpenRouter provider
@llm-provider-specialist Implement Google Gemini provider
```

**Key Responsibilities**:

- Implements `BaseLLMProvider` interface (4 required methods)
- Handles sync/async generation and streaming
- Implements retry logic with exponential backoff
- Raises specific exceptions from `llm.exceptions`
- Uses `httpx` for HTTP clients (async support)
- Never logs API keys or secrets

---

## Agent Design Principles

All AICA custom agents follow these core principles:

### 1. Single Role

Each agent has one focused responsibility. No "Swiss-army knife" agents.

### 2. Minimal Tools

Agents only get the tools they need for their specific role:

- **Explorer**: Read-only (`read`, `search`)
- **Detector/Provider Specialists**: Code editing (`read`, `search`, `edit`)
- No agents have terminal execution unless absolutely necessary

### 3. Clear Boundaries

Each agent explicitly defines what it should NOT do:

- Explorer never modifies code
- Detector Specialist never modifies target repositories
- Provider Specialist never logs secrets

### 4. Keyword-Rich Descriptions

Agent descriptions include trigger phrases so the main agent knows when to delegate:

- "Use when: adding new detector, fixing detector bugs..."
- "Use when: researching architecture patterns, understanding code flow..."

### 5. Consistent Patterns

All agents enforce AICA's architectural rules:

- Import order: `from __future__ import annotations` first
- Type hints on all function signatures
- Structured logging with `get_logger()`
- Never use `print()` or stdlib `logging`
- Use `Path` not `str` for file paths

---

## Creating New Agents

To create a new custom agent for AICA:

1. **Identify the specialized role**: What specific task needs focused expertise?

2. **Choose minimal tools**: What's the bare minimum needed?
   - Research only → `[read, search]`
   - Code changes → `[read, search, edit]`
   - System commands → `[read, search, edit, execute]`

3. **Define boundaries**: What should this agent NEVER do?

4. **Write keyword-rich description**: Include trigger phrases for `"Use when: ..."`

5. **Create the file**: `.github/agents/<name>.agent.md`

6. **Test invocation**: Try invoking as subagent with various prompts

7. **Update this document**: Add the new agent to the list above

### Template

```markdown
---
description: "Specialist for {specific task}. Use when: {trigger1}, {trigger2}, {trigger3}."
tools: [{minimal set}]
user-invocable: true
name: "{Agent Name}"
argument-hint: "{What input does this agent need?}"
---

You are an AICA {Role Name}. Your sole focus is {specific responsibility}.

## Your Role
{Clear purpose statement}

## Core {Pattern/Process} (MANDATORY)
{Step-by-step approach or rules}

## Critical Rules
1. {Rule 1}
2. {Rule 2}
3. {Rule 3}

## NEVER Do This
- ❌ {Anti-pattern 1}
- ❌ {Anti-pattern 2}
- ❌ {Anti-pattern 3}
```

---

## Invocation Methods

### Method 1: Explicit Mention (Manual)

Use the `@agent-name` syntax in chat:

```
@detector-specialist Create a detector for API routes
```

### Method 2: Automatic Delegation (Subagent)

The main agent automatically delegates based on description matching:

```
User: "Add support for detecting tRPC routers"
→ Main agent sees "detector" in request
→ Invokes Detector Specialist automatically
```

### Method 3: Using runSubagent Tool

From within another agent or workflow:

```python
runSubagent(
    agentName="Detector Specialist",
    description="Create new detector",
    prompt="Implement a detector for Server Components in Next.js 16"
)
```

---

## Best Practices

### ✅ Do This

- **Invoke specialists for their domain**: Let experts handle specialized tasks
- **Use Explorer before editing**: Research first, then modify
- **Combine agents in workflows**: Explorer → Specialist → Review
- **Trust agent outputs**: Specialists follow strict patterns
- **Provide context in prompts**: "Based on existing routes detector, add support for..."

### ❌ Don't Do This

- **Don't ask Explorer to edit code**: It's read-only
- **Don't ask specialists to do research**: They focus on implementation
- **Don't override agent patterns**: They enforce architectural rules
- **Don't bypass agents for specialized tasks**: Use the specialist

---

## Troubleshooting

### Agent Not Being Invoked

**Problem**: Asked for detector work but Detector Specialist wasn't invoked

**Solutions**:

1. Use explicit mention: `@detector-specialist ...`
2. Include trigger keywords: "add new detector", "fix detector bug"
3. Check agent description has relevant keywords

### Agent Gives Generic Response

**Problem**: Agent response doesn't follow strict patterns

**Solutions**:

1. Check agent file has clear constraints and rules
2. Verify tool restrictions are enforced
3. Update agent body with more specific instructions

### Need New Agent

**Problem**: Repeated manual work that could be automated

**Signals you need a new agent**:

- Same instructions given multiple times
- Specific tool restrictions needed repeatedly
- Domain expertise required frequently
- Context isolation would help (subagent with single output)

**Action**: Follow "Creating New Agents" section above

---

## Maintenance

### Updating Agents

When AICA patterns evolve:

1. Update agent instructions to reflect new patterns
2. Add new rules to "Critical Rules" section
3. Update examples with current best practices
4. Test with representative tasks

### Deprecating Agents

When an agent is no longer needed:

1. Mark as deprecated in description
2. Remove from this document
3. Archive file (don't delete immediately)
4. Update any workflows that reference it

---

## Related Documentation

- [Custom Agents Reference](https://code.visualstudio.com/docs/copilot/customization/custom-agents)
- [AICA Coding Guidelines](./copilot-instructions.md)
- [Detector Workflow Skill](./.github/skills/detector-workflow/SKILL.md)
- [LLM Provider Testing Skill](./.github/skills/llm-provider-testing/SKILL.md)
- [Vector Store Workflow Skill](./.github/skills/vector-store-workflow/SKILL.md)
