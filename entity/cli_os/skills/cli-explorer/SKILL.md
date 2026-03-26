---
name: cli-explorer
description: >
  CLI exploration and experimentation skill — guides the agent in exploring
  the system, creating experiments, managing workspaces, and building projects
  from scratch in an interactive terminal environment.
---

# CLI Explorer — System Discovery & Experimentation

A comprehensive guide for exploring your CLI-OS environment, running experiments,
and managing your workspace like a pro sysadmin.

---

## System Discovery

When you first enter the environment (or wake up in a new session), orient yourself:

```bash
# Who am I? Where am I?
whoami && hostname && pwd

# What's available?
which python3 python node npm pip git curl 2>/dev/null

# System info
uname -a
python3 --version 2>/dev/null
node --version 2>/dev/null

# Disk space
df -h . 2>/dev/null || du -sh playground/ 2>/dev/null
```

### Checking Your Workspace

```bash
# What projects exist?
find playground/projects -maxdepth 1 -type d 2>/dev/null | sort

# Any work in progress?
find playground/tmp -type f -newer playground/tmp -mmin -60 2>/dev/null

# Recent output
ls -lt playground/output/ 2>/dev/null | head -10
```

---

## Project Templates

### Quick Python Project

```bash
PROJECT="playground/projects/my-project"
mkdir -p "$PROJECT"/{src,tests,data}
cat > "$PROJECT/src/main.py" << 'PY'
#!/usr/bin/env python3
"""Main entry point."""

def main():
    print("Hello from my-project!")

if __name__ == "__main__":
    main()
PY
chmod +x "$PROJECT/src/main.py"
python3 "$PROJECT/src/main.py"
```

### Quick Web Server

```bash
cat > playground/tmp/server.py << 'PY'
#!/usr/bin/env python3
"""Minimal HTTP server."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

os.chdir("playground/output")
print("Serving on http://localhost:8888")
HTTPServer(("", 8888), SimpleHTTPRequestHandler).serve_forever()
PY
```

### Data Pipeline

```bash
# Fetch → Transform → Store
curl -s "https://api.example.com/data" \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print(json.dumps(data, indent=2))" \
  > playground/output/data.json
```

---

## Experimentation Patterns

### Try-and-Learn Loop

1. **Hypothesis**: "I think X works like Y"
2. **Experiment**: Write a small script to test
3. **Observe**: Run it, look at the output
4. **Conclude**: Update your understanding

```bash
# Example: testing Python's asyncio behavior
cat > playground/tmp/experiment.py << 'PY'
import asyncio

async def task(name, delay):
    print(f"{name} starting")
    await asyncio.sleep(delay)
    print(f"{name} done after {delay}s")

async def main():
    await asyncio.gather(
        task("A", 0.1),
        task("B", 0.05),
        task("C", 0.15),
    )
    print("All done!")

asyncio.run(main())
PY
python3 playground/tmp/experiment.py
```

### Benchmarking

```bash
# Time a Python operation
python3 -c "
import time
start = time.perf_counter()
result = sum(range(10_000_000))
elapsed = time.perf_counter() - start
print(f'Sum: {result}')
print(f'Time: {elapsed:.4f}s')
"
```

### File Processing

```bash
# Count lines, words, characters
wc playground/projects/*/src/*.py 2>/dev/null

# Find large files
find playground/ -type f -size +1M 2>/dev/null

# Search for patterns
grep -rn "TODO\|FIXME\|HACK" playground/projects/ 2>/dev/null
```

---

## Workspace Management

### Cleanup

```bash
# Clean tmp (older than 1 day)
find playground/tmp -type f -mtime +1 -delete 2>/dev/null

# Show disk usage by project
du -sh playground/projects/*/ 2>/dev/null | sort -rh
```

### Backup / Snapshot

```bash
# Create a snapshot of a project
PROJ="my-project"
STAMP=$(date +%Y%m%d_%H%M%S)
tar czf "playground/output/${PROJ}_${STAMP}.tar.gz" \
    -C playground/projects "$PROJ"
echo "Snapshot saved: playground/output/${PROJ}_${STAMP}.tar.gz"
```

### Git for Projects

```bash
cd playground/projects/my-project
git init
git add -A
git commit -m "Initial commit"
git log --oneline
```

---

## Advanced Recipes

### Run a Background Process

```bash
# Start a long-running task
nohup python3 playground/tmp/long_task.py > playground/output/task.log 2>&1 &
echo "PID: $!"

# Check on it later
ps aux | grep long_task
tail -f playground/output/task.log
```

### Create a CLI Tool

```bash
cat > playground/projects/tools/greet << 'SH'
#!/usr/bin/env bash
# Usage: greet [NAME]
NAME="${1:-World}"
echo "👋 Hello, $NAME! Welcome to CLI-OS."
echo "Current time: $(date)"
echo "Uptime: $(uptime 2>/dev/null || echo 'N/A')"
SH
chmod +x playground/projects/tools/greet
playground/projects/tools/greet "Agent"
```

### Interactive Data Exploration

```bash
python3 << 'PY'
import json, os

# List all JSON files in output
json_files = [f for f in os.listdir("playground/output") if f.endswith(".json")]
print(f"Found {len(json_files)} JSON files:")
for f in sorted(json_files):
    size = os.path.getsize(f"playground/output/{f}")
    print(f"  {f} ({size:,} bytes)")
PY
```

---

## Tips & Tricks

- **Use `state_diff`** to track changes between experiments — snapshot your output and compare
- **Use `fetch_url`** to grab documentation or API responses
- **Use `web_search`** to find solutions when stuck
- **Use `app_notify`** to leave yourself persistent notes that survive across sessions
- **Pipe everything** — `cmd1 | cmd2 | cmd3` is your best friend
- **Save useful scripts** to `playground/projects/tools/` for reuse
- **Document as you go** — add README.md files to your projects

---

## When You're Bored

Try building one of these:
- A Mandelbrot set renderer in Python
- A simple chat bot that responds to keywords
- A file organiser that sorts downloads by type
- A weather dashboard using a public API
- A markdown-to-HTML converter
- A port scanner
- A simple key-value store with a REST API
- A code snippet manager
