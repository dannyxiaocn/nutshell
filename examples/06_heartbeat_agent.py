"""Example 06: Long-running Instance with built-in heartbeat."""
import asyncio
from nutshell import Instance, Agent, AnthropicProvider


async def main():
    agent = Agent(
        system_prompt=(
            "You are a task processor. On each activation: "
            "use read_kanban to see tasks, do the work, "
            "then write_kanban to update (remove done, leave pending with notes). "
            "Call write_kanban('') when all tasks are complete."
        ),
        model="claude-haiku-4-5-20251001",
        provider=AnthropicProvider(),
    )

    instance = Instance(
        agent=agent,
        heartbeat=20.0,  # short interval for testing; default is 900s
        on_tick=lambda r: print(f"[tick] kanban empty: {instance.is_done()}"),
        on_done=lambda: print("[done] Kanban cleared!"),
    )
    print(f"Instance: {instance.instance_dir}")

    async with instance:
        # Seed kanban (direct file write)
        instance.kanban_path.write_text(
            "- Summarize recursion in one sentence\n"
            "- List 3 benefits of async programming\n"
            "- Time complexity of binary search?\n",
            encoding="utf-8",
        )

        # Add a task mid-run (will be picked up on next heartbeat tick)
        await asyncio.sleep(5)
        current = instance.kanban_path.read_text(encoding="utf-8")
        instance.kanban_path.write_text(
            current + "- Define what a heartbeat mechanism does\n", encoding="utf-8"
        )
        print("[main] Added task — waiting for next heartbeat tick")

        # Wait for heartbeat to finish all tasks
        await instance._heartbeat_task

    print(f"\nKanban:  {instance.kanban_path}")
    print(f"Context: {instance.instance_dir / 'context.json'}")


if __name__ == "__main__":
    asyncio.run(main())
