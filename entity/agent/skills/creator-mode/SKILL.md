---
name: creator-mode
description: >
  Create or modify tools (.json + .sh pairs) and skills (SKILL.md files)
  and hot-reload them into the active conversation using reload_capabilities.
  Use when you want to build a new capability, fix an existing tool, or update
  a skill and test it immediately without restarting.
---

## Overview

Session-scoped tools and skills live in `core/` inside your session directory:

- **Tools**: `core/tools/<name>.json` (schema) + `core/tools/<name>.sh` (implementation)
- **Skills**: `core/skills/<name>/SKILL.md` (frontmatter + body)

After creating or editing these files, call `reload_capabilities` to make the changes available in the current conversation. No restart needed.

## Creating a tool

1. Write the JSON schema to `core/tools/<name>.json`
2. Write the shell implementation to `core/tools/<name>.sh`
3. Make the script executable: `chmod +x core/tools/<name>.sh`
4. Call `reload_capabilities`
5. Test the tool by calling it

### Tool JSON schema template

```json
{
  "name": "my_tool",
  "description": "What this tool does.",
  "input_schema": {
    "type": "object",
    "properties": {
      "arg1": {
        "type": "string",
        "description": "Description of arg1."
      }
    },
    "required": ["arg1"]
  }
}
```

### Shell tool contract

- All tool arguments arrive as a JSON object on **stdin**
- Write the result to **stdout**
- Exit 0 = success; non-zero exit = error (stderr returned as error message)
- Timeout: 30 seconds
- Output cap: 10 000 characters

Example shell tool that reads `arg1` from stdin:

```bash
#!/usr/bin/env bash
set -euo pipefail
input=$(cat)
arg1=$(echo "$input" | python3 -c "import sys, json; print(json.load(sys.stdin)['arg1'])")
echo "You passed: $arg1"
```

## Modifying a tool or skill

1. Edit the file directly with `bash` (e.g., `sed -i`, heredoc, or a Python script)
2. Call `reload_capabilities`
3. Test the change

## The iteration loop

```
draft → reload_capabilities → test → revise → reload_capabilities → test → …
```

Repeat until the tool or skill behaves as intended. Each reload replaces the previous version in memory.

## Gotchas

- `reload_capabilities` itself cannot be overridden — it is always injected last and any disk-based tool with the same name is filtered out.
- Session tools override entity tools of the same name — use this intentionally to patch a built-in without touching entity files.
- Skills are fully reloaded on each `reload_capabilities` call — changes to `SKILL.md` take effect immediately.
