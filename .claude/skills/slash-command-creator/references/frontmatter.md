# Slash Command Frontmatter Reference

## Required Fields

### `description`
Brief description of what the command does. Shown in `/help` output.

```yaml
description: Create a git commit with staged changes
```

## Optional Fields

### `allowed-tools`
Specifies which tools the command can use. Format: `ToolName(pattern:*)` or just `ToolName`.

```yaml
# Single tool
allowed-tools: Bash(git status:*)

# Multiple tools
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*)

# Tool without pattern
allowed-tools: Read, Write, Edit
```

Common tool patterns:
- `Bash(command:*)` - Allow specific bash commands
- `Read` - File reading
- `Write` - File writing
- `Edit` - File editing
- `Grep` - Content search
- `Glob` - File pattern matching

### `argument-hint`
Shows expected arguments when auto-completing the command.

```yaml
# Single argument
argument-hint: [message]

# Multiple arguments
argument-hint: [pr-number] [priority] [assignee]

# Alternative syntax
argument-hint: add [tagId] | remove [tagId] | list
```

### `model`
Specific model to use for this command. See [Models overview](https://docs.claude.com/en/docs/about-claude/models/overview).

```yaml
model: claude-haiku-4-5-20251001
model: claude-sonnet-4-5-20250929
```

### `disable-model-invocation`
Prevents the `SlashCommand` tool from calling this command programmatically.

```yaml
disable-model-invocation: true
```

## Complete Frontmatter Example

```yaml
---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*)
argument-hint: [message]
description: Create a git commit with staged changes
model: claude-haiku-4-5-20251001
---
```
