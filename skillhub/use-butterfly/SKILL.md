---
name: use-butterfly
description: >
  Butterfly CLI usage guide. Load this skill when the user asks how to use
  butterfly, wants to run CLI commands, manage sessions, create entities,
  view logs, or interact with the butterfly agent system from the terminal.
---

# Butterfly CLI Guide

Butterfly is a minimal Python agent runtime. Agents persist across conversations via filesystem-based sessions.

## Core Concepts

- **Entity** — a reusable agent template (`entity/<name>/`): config, prompts, tools, skills
- **Session** — a running instance of an entity (`sessions/<id>/`): agent-visible workspace
- **Meta session** — mutable shared seed for all sessions of an entity (`sessions/<entity>_meta/`)
- **Server** — background daemon that watches for sessions and runs agent loops

## Quick Start

```bash
# Start the server (auto-daemonizes)
butterfly server
# or directly:
butterfly-server start

# Send a message (auto-starts server if needed)
butterfly chat "Hello, what can you do?"

# Use a specific entity
butterfly chat --entity butterfly_dev "Review the codebase"

# Continue an existing session
butterfly chat --session 2026-04-13_10-00-00-a1b2 "What's the status?"
```

## All CLI Commands

### Session Interaction

| Command | Description |
|---------|-------------|
| `butterfly chat MESSAGE` | Send a message; creates a new session or continues one |
| `butterfly new [ID]` | Create a session without sending a message |
| `butterfly stop SESSION_ID` | Stop a session's heartbeat loop |
| `butterfly start SESSION_ID` | Resume a stopped session |

**`chat` flags:**
- `--session ID` — continue an existing session
- `--entity NAME` — entity to use (default: `agent`)
- `--no-wait` — fire-and-forget (don't block for reply)
- `--timeout N` — seconds to wait (default: 300)
- `--keep-alive` — keep server running after reply
- `--inject-memory KEY=VALUE` or `KEY=@FILE` — inject memory layers

**`new` flags:**
- `--entity NAME` — entity to init from (default: `agent`)
- `--heartbeat N` — heartbeat interval in seconds
- `--inject-memory KEY=VALUE` — inject memory at creation

### Monitoring & Views

| Command | Description |
|---------|-------------|
| `butterfly sessions` | List all sessions with status |
| `butterfly log [SESSION_ID]` | Show conversation history |
| `butterfly tasks [SESSION_ID]` | Show task cards |

**`log` flags:**
- `-n N` — number of turns (default: 5)
- `--since TIMESTAMP` — filter by time (ISO-8601, epoch, or `now`)
- `--watch` — poll for new turns every 2s

### Entity Management

| Command | Description |
|---------|-------------|
| `butterfly entity new` | Scaffold a new entity (interactive) |

**`entity new` flags:**
- `-n NAME` — skip interactive prompt
- `--init-from SOURCE` — copy from existing entity
- `--blank` — empty entity with placeholders

### Server Management

| Command | Description |
|---------|-------------|
| `butterfly server` | Start the server daemon |
| `butterfly-server start` | Start server (auto-daemonizes) |
| `butterfly-server stop` | Stop the server |
| `butterfly-server status` | Check if server is running |
| `butterfly-server update` | Stop, reinstall, restart |
| `butterfly-server --foreground` | Run in current process |

## Session Lifecycle

```
entity/ ──create──> sessions/<id>/ ──chat──> agent runs ──stop──> napping
                                                  ↑                  │
                                                  └────start─────────┘
```

1. `butterfly new` or `butterfly chat` creates a session from an entity template
2. Server picks up the session and runs the agent loop
3. Agent reads/writes `core/` files (memory, tasks, tools, skills)
4. `butterfly stop` pauses; `butterfly start` resumes

## Practical Workflows

**Quick one-shot question:**
```bash
butterfly chat "Explain how Python generators work"
```

**Long-running dev session:**
```bash
butterfly new --entity butterfly_dev my-feature
butterfly chat --session my-feature "Add pagination to the API"
butterfly log --session my-feature --watch  # monitor progress
```

**Inject context into a session:**
```bash
butterfly chat --inject-memory spec=@design_doc.md "Implement this spec"
```

**Check all agent activity:**
```bash
butterfly sessions              # list all sessions with status
butterfly tasks <SESSION_ID>    # inspect a specific session's task board
```
