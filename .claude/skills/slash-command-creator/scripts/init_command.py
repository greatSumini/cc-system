#!/usr/bin/env python3
"""
Slash Command Initializer - Creates a new slash command from template

Usage:
    init_command.py <command-name> [--scope project|personal] [--path <custom-path>]

Examples:
    init_command.py review                    # Creates .claude/commands/review.md
    init_command.py deploy --scope personal   # Creates ~/.claude/commands/deploy.md
    init_command.py test --path ./my-commands # Creates ./my-commands/test.md
"""

import sys
import os
from pathlib import Path
import argparse


COMMAND_TEMPLATE = '''---
description: {description}
---

# {command_title}

{body}
'''

COMMAND_TEMPLATE_WITH_TOOLS = '''---
allowed-tools: {allowed_tools}
description: {description}
---

# {command_title}

{body}
'''

COMMAND_TEMPLATE_FULL = '''---
allowed-tools: {allowed_tools}
argument-hint: {argument_hint}
description: {description}
model: {model}
---

# {command_title}

{body}
'''


def title_case(name: str) -> str:
    """Convert hyphenated name to Title Case."""
    return ' '.join(word.capitalize() for word in name.replace('-', ' ').split())


def get_project_commands_path() -> Path:
    """Get the project-level commands directory."""
    return Path.cwd() / '.claude' / 'commands'


def get_personal_commands_path() -> Path:
    """Get the user-level commands directory."""
    return Path.home() / '.claude' / 'commands'


def init_command(
    command_name: str,
    scope: str = 'project',
    custom_path: str = None,
    description: str = None,
    body: str = None,
    allowed_tools: str = None,
    argument_hint: str = None,
    model: str = None,
    namespace: str = None
) -> Path:
    """
    Initialize a new slash command.

    Args:
        command_name: Name of the command (without .md extension)
        scope: 'project' or 'personal'
        custom_path: Optional custom path override
        description: Command description
        body: Command body content
        allowed_tools: Comma-separated list of allowed tools
        argument_hint: Hint for command arguments
        model: Specific model to use
        namespace: Optional subdirectory namespace

    Returns:
        Path to created command file, or None if error
    """
    # Determine base path
    if custom_path:
        base_path = Path(custom_path).resolve()
    elif scope == 'personal':
        base_path = get_personal_commands_path()
    else:
        base_path = get_project_commands_path()

    # Add namespace subdirectory if specified
    if namespace:
        base_path = base_path / namespace

    # Create directory if it doesn't exist
    try:
        base_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {base_path}: {e}")
        return None

    # Create command file path
    command_file = base_path / f'{command_name}.md'

    # Check if file already exists
    if command_file.exists():
        print(f"Error: Command already exists: {command_file}")
        return None

    # Prepare content
    command_title = title_case(command_name)
    description = description or f"[TODO: Brief description of /{command_name}]"
    body = body or f"[TODO: Add instructions for /{command_name}]\n\n$ARGUMENTS"

    # Choose template based on options
    if allowed_tools and argument_hint and model:
        content = COMMAND_TEMPLATE_FULL.format(
            allowed_tools=allowed_tools,
            argument_hint=argument_hint,
            description=description,
            model=model,
            command_title=command_title,
            body=body
        )
    elif allowed_tools:
        content = COMMAND_TEMPLATE_WITH_TOOLS.format(
            allowed_tools=allowed_tools,
            description=description,
            command_title=command_title,
            body=body
        )
    else:
        content = COMMAND_TEMPLATE.format(
            description=description,
            command_title=command_title,
            body=body
        )

    # Write command file
    try:
        command_file.write_text(content)
        print(f"Created: {command_file}")
        return command_file
    except Exception as e:
        print(f"Error writing command file: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Initialize a new Claude Code slash command',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s review
      Creates .claude/commands/review.md (project command)

  %(prog)s deploy --scope personal
      Creates ~/.claude/commands/deploy.md (personal command)

  %(prog)s component --namespace frontend
      Creates .claude/commands/frontend/component.md

  %(prog)s commit --allowed-tools "Bash(git add:*), Bash(git commit:*)"
      Creates command with specific tool permissions

Command naming:
  - Use lowercase with hyphens (e.g., 'review-pr', 'run-tests')
  - Avoid spaces and special characters
  - Keep names concise and descriptive
'''
    )

    parser.add_argument('command_name', help='Name of the slash command (without .md)')
    parser.add_argument('--scope', choices=['project', 'personal'], default='project',
                        help='Command scope: project (.claude/commands) or personal (~/.claude/commands)')
    parser.add_argument('--path', dest='custom_path', help='Custom path for command file')
    parser.add_argument('--namespace', help='Subdirectory namespace (e.g., frontend, backend)')
    parser.add_argument('--description', help='Command description')
    parser.add_argument('--allowed-tools', dest='allowed_tools', help='Comma-separated list of allowed tools')
    parser.add_argument('--argument-hint', dest='argument_hint', help='Hint for command arguments')
    parser.add_argument('--model', help='Specific model to use (e.g., claude-haiku-4-5-20251001)')

    args = parser.parse_args()

    result = init_command(
        command_name=args.command_name,
        scope=args.scope,
        custom_path=args.custom_path,
        description=args.description,
        allowed_tools=args.allowed_tools,
        argument_hint=args.argument_hint,
        model=args.model,
        namespace=args.namespace
    )

    if result:
        print(f"\nSlash command '/{args.command_name}' initialized successfully!")
        print("\nNext steps:")
        print("1. Edit the command file to update the description and body")
        print("2. Test the command by running it in Claude Code")
        print(f"\nUsage: /{args.command_name} [arguments]")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
