# Nutshell CLI Bug Backlog

*Updated: 2026-04-10*

只保留未解决问题，以及待验证的修复方向。

---

## Bug 3: `nutshell log/tasks/prompt-stats/token-report` 默认 session 可能落到 meta session，而不是最近聊天 session [低危]

### 现象
不显式传 `session_id` 时，默认 session 来自 `_sort_sessions()[0]`。
当前排序会把运行中的 meta session 和普通聊天 session 混排，因此某些情况下：

```bash
nutshell log
```

看到的是 `<entity>_meta`，而不是用户刚刚聊天的那个 session。

### 根因
这些命令在未传 `session_id` 时，都会走 `ui/cli/main.py` 中的 `_read_all_sessions(...)[0]`。
而 `_read_all_sessions()` 最终调用 `ui/web/sessions.py` 的 `_sort_sessions()`；当前排序只按状态优先级和 `last_run_at/created_at` 排序，没有把 meta session 从“默认聊天目标”候选里排除。

### 待验证修复方向
- 给这些“默认取最近 session”的 CLI 命令增加 `exclude_meta=True` 的选择逻辑。
- 或把“最近 session”拆成两套语义：
  `sessions/friends` 保留全量排序，`log/tasks/prompt-stats/token-report` 默认优先 non-meta session。

---

## Bug 10: `nutshell visit` 默认 session 可能落到 meta session，而不是最近聊天 session [低危]

### 现象
不显式传 `session_id` 时：

```bash
nutshell visit
```

可能直接打开 `<entity>_meta`，而不是用户最近使用的普通聊天 session。

### 根因
`ui/cli/visit.py` 没有复用 `_read_all_sessions()`，而是直接对 `_sessions/` 下目录名做 `sorted(..., reverse=True)`，取字典序最后一个目录。
这会把形如 `zz_agent_meta` 或其他字典序更靠后的 meta session 选为默认目标。

### 待验证修复方向
- 让 `visit` 复用与其他 CLI 一致的 session 选择逻辑，并显式排除 meta session。
- 或在 `visit` 的默认选择路径中增加 non-meta 过滤。

---

## Bug 5: `nutshell entity new -n NAME` 仍会触发交互式 parent 询问 [低危]

### 现象
```bash
nutshell entity new -n my-agent
```

仍会继续询问 `Extend which entity?`；在非交互环境下会直接失败。

### 根因
`-n/--name` 只绕过了名称输入，没有绕过 parent 选择。若未显式给 `--extends` 或 `--standalone`，流程仍会进入 `_ask_parent()`。

### 待验证修复方向
- 增加 `--parent NAME`。
- 或在 `-n NAME` 且未指定 `--extends/--standalone` 时，默认采用 `--extends agent`。
