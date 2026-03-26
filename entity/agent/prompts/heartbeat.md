Heartbeat activation — you were napping and just woke up.

<current_tasks>
{tasks}
</current_tasks>

Resume work from where you left off. Focus on the highest-priority incomplete item.

<after_this_activation>
- **Work remains** → update the task board with progress notes your future self can resume from. Adjust `heartbeat_interval` in `params.json` via bash if needed.
- **All done** → clear the board: `echo -n > core/tasks.md` — then respond with exactly: SESSION_FINISHED
</after_this_activation>
