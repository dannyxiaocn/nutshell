# UI — Implementation

## Subdirectories

- `cli/`: the `butterfly` command-line interface
- `web/`: FastAPI, SSE streaming, optional WeChat bridge

## Usage

```bash
butterfly chat "hello"
butterfly sessions
butterfly web
```

The runtime can run without this directory, but this is how operators create sessions, inspect them, and send messages.
