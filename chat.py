#!/usr/bin/env python3
"""Nutshell interactive CLI chat.

Usage:
    python chat.py
    python chat.py --entity entity/agent_core
    python chat.py --model claude-sonnet-4-6
    python chat.py --api-key sk-ant-...
    python chat.py --resume 2026-03-07_14-30-00
    python chat.py --heartbeat 20

Commands during chat:
    /clear      Clear conversation history
    /system     Print current system prompt
    /system <p> Change system prompt to <p>
    /tools      List loaded tools
    /skills     List loaded skills
    /kanban     Show current kanban board
    /exit       Exit
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent
_DEFAULT_ENTITY = _REPO_ROOT / "entity" / "chat_core"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Nutshell interactive CLI chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--entity", "-e",
        default=str(_DEFAULT_ENTITY),
        metavar="DIR",
        help=f"Entity directory containing agent.yaml (default: entity/chat_core)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model ID override (default: from agent.yaml)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ANTHROPIC_API_KEY"),
        help="Anthropic API key (default: ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--resume",
        default=None,
        metavar="INSTANCE_ID",
        help="Resume an existing instance by ID (e.g. 2026-03-07_14-30-00)",
    )
    parser.add_argument(
        "--heartbeat",
        default=None,
        type=float,
        metavar="SECONDS",
        help="Override heartbeat interval in seconds (default: 900). e.g. --heartbeat 20 for testing",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    return parser.parse_args()


# ANSI color helpers
def _supports_color(no_color: bool) -> bool:
    return not no_color and sys.stdout.isatty()


class Colors:
    def __init__(self, enabled: bool):
        self.e = enabled

    def _c(self, code, text):
        return f"\033[{code}m{text}\033[0m" if self.e else text

    def bold(self, t):    return self._c("1", t)
    def dim(self, t):     return self._c("2", t)
    def cyan(self, t):    return self._c("36", t)
    def green(self, t):   return self._c("32", t)
    def yellow(self, t):  return self._c("33", t)
    def red(self, t):     return self._c("31", t)
    def magenta(self, t): return self._c("35", t)


def print_banner(c: Colors, agent, entity: str, instance_dir, heartbeat: float):
    system_preview = agent.system_prompt if len(agent.system_prompt) <= 60 else agent.system_prompt[:57] + "..."
    print(c.bold(c.cyan("╭─────────────────────────────────────────╮")))
    print(c.bold(c.cyan("│          nutshell  chat  cli             │")))
    print(c.bold(c.cyan("╰─────────────────────────────────────────╯")))
    print(c.dim(f"  entity    : {entity}"))
    print(c.dim(f"  model     : {agent.model}"))
    print(c.dim(f"  system    : {system_preview}"))
    print(c.dim(f"  instance  : {instance_dir}"))
    print(c.dim(f"  heartbeat : {heartbeat}s"))
    if agent.tools:
        print(c.dim(f"  tools     : {', '.join(t.name for t in agent.tools)}"))
    if agent.skills:
        print(c.dim(f"  skills    : {', '.join(s.name for s in agent.skills)}"))
    print(c.dim("  /clear /system /tools /skills /kanban /exit"))
    print()


async def chat_loop(args):
    from nutshell import AgentLoader, AnthropicProvider, Instance

    if not args.api_key:
        print("Error: no API key. Set ANTHROPIC_API_KEY or use --api-key.", file=sys.stderr)
        sys.exit(1)

    entity_path = Path(args.entity)
    if not entity_path.exists():
        print(f"Error: entity directory not found: {entity_path}", file=sys.stderr)
        sys.exit(1)

    agent = AgentLoader().load(entity_path)
    agent._provider = AnthropicProvider(api_key=args.api_key)
    if args.model:
        agent.model = args.model

    c = Colors(_supports_color(args.no_color))
    prompt = c.bold(c.green("you  ❯ "))

    from nutshell.core.instance import DEFAULT_HEARTBEAT_INTERVAL
    effective_heartbeat = args.heartbeat if args.heartbeat is not None else DEFAULT_HEARTBEAT_INTERVAL
    kwargs = dict(agent=agent, heartbeat=effective_heartbeat)
    instance = Instance.resume(args.resume, **kwargs) if args.resume else Instance(**kwargs)

    print_banner(c, agent, args.entity, instance.instance_dir, effective_heartbeat)

    # ── Chat loop (blocking input — heartbeat does not run during chat) ──
    while True:
        try:
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{c.dim('Bye!')}")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/exit", "/quit", "/q"):
            print(c.dim("Bye!"))
            break

        if user_input.lower() == "/clear":
            agent.close()
            print(c.yellow("  History cleared."))
            continue

        if user_input.lower() == "/tools":
            if agent.tools:
                print(c.yellow(f"  Tools: {', '.join(t.name for t in agent.tools)}"))
            else:
                print(c.yellow("  No tools loaded."))
            continue

        if user_input.lower() == "/skills":
            if agent.skills:
                print(c.yellow(f"  Skills: {', '.join(s.name for s in agent.skills)}"))
            else:
                print(c.yellow("  No skills loaded."))
            continue

        if user_input.lower() == "/kanban":
            content = instance.kanban_path.read_text(encoding="utf-8").strip()
            if content:
                print(c.yellow(f"  Kanban:\n{content}"))
            else:
                print(c.yellow("  Kanban is empty."))
            continue

        if user_input.lower() == "/system":
            print(c.yellow(f"  System: {agent.system_prompt}"))
            continue

        if user_input.lower().startswith("/system "):
            new_prompt = user_input[8:].strip()
            agent.system_prompt = new_prompt
            agent.close()
            print(c.yellow("  System prompt updated. History cleared."))
            continue

        if user_input.startswith("/"):
            print(c.red(f"  Unknown command: {user_input}"))
            continue

        try:
            print(c.dim("  thinking..."), end="\r")
            result = await instance.chat(user_input)
            print(" " * 20, end="\r")

            for tc in result.tool_calls:
                print(c.magenta(f"  [tool] {tc.name}({tc.input})"))

            print(c.bold(c.cyan("agent❯ ")) + result.content)
            print()

        except Exception as exc:
            print(c.red(f"  Error: {exc}"))

    # ── Chat UI exited — start heartbeat now ────────────────────────────
    if not instance.is_done():
        instance._on_tick = lambda r: print(f"\n{c.bold(c.yellow('auto ❯ '))}{r.content}\n", flush=True)
        instance._on_done = lambda: print(c.dim("  [heartbeat] Kanban cleared — all tasks done.\n"), flush=True)
        print(c.dim(f"  Instance continues running: {instance.instance_dir}"))
        await instance.start()
        await instance._heartbeat_task
    else:
        instance.close()


def main():
    args = parse_args()
    asyncio.run(chat_loop(args))


if __name__ == "__main__":
    main()
