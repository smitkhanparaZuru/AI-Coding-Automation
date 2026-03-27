# Detector Workflow Skill

Complete workflow for creating, testing, and integrating repository scanner detectors in AICA.

## Quick Start

Invoke this skill with a slash command:

```
/detector-workflow Create a detector for Next.js middleware files
```

Or mention it in conversation:

```
I need to add a detector for API routes. Can you help with the detector-workflow?
```

## What This Skill Provides

### 📋 Complete 8-Step Workflow

1. Plan detection strategy
2. Create detector file with proper structure
3. Implement detection logic
4. Integrate with scanner core
5. Create comprehensive tests
6. Run and validate tests
7. Test full integration
8. Document the detector

### 📚 Reference Materials

- [Common Patterns](./references/patterns.md) - File globbing, path handling, content parsing, logging patterns
- Quality checklist with 12 validation points
- Common pitfalls and how to avoid them

### ✅ Ensures AICA Compliance

- Structured logging with `get_logger()`
- Relative path handling
- Proper error handling
- ABC patterns and type hints
- Test coverage >80%

## Structure

```
.github/skills/detector-workflow/
├── SKILL.md              # Main workflow guide
├── references/
│   └── patterns.md       # Common detector patterns
└── README.md            # This file
```

## Example Detectors to Reference

Browse existing detectors for patterns:

- `aica/repo_intelligence/scanner/detectors/routes.py` - Complex route detection
- `aica/repo_intelligence/scanner/detectors/component.py` - Component classification
- `aica/repo_intelligence/scanner/detectors/package.py` - JSON file parsing

## When to Use vs @detector-specialist Agent

| Use Case                  | Choose                       |
| ------------------------- | ---------------------------- |
| Learning the workflow     | `@detector-workflow` skill   |
| Step-by-step guidance     | `@detector-workflow` skill   |
| Quick reference           | `@detector-workflow` skill   |
| Implementing the detector | `@detector-specialist` agent |
| Fixing detector bugs      | `@detector-specialist` agent |

**Typical workflow:**

1. Read the skill: `/detector-workflow` to understand the process
2. Implement with agent: `@detector-specialist Create the middleware detector`

## Testing the Skill

After creation, verify it works:

```bash
# The skill should appear in VS Code Copilot Chat
# Type "/" to see the slash command list
# "detector-workflow" should be listed
```

## Maintenance

When AICA conventions change:

1. Update [SKILL.md](./SKILL.md) with new patterns
2. Update [patterns.md](./references/patterns.md) with examples
3. Test with a sample detector creation
