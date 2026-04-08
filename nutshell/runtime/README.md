# nutshell/runtime

中央调度层：启动 server、发现并管理 session、提供 IPC 通信基础设施。

## 文件列表
- `server.py`：runtime server 入口，启动 watcher 后台服务。
- `watcher.py`：轮询 `_sessions/`，自动发现并拉起 session daemon（asyncio task）。
- `ipc.py`：基于文件的 IPC 实现（FileIPC）；读写 `events.jsonl`、`context.jsonl`，包含 display event 转换器。
- `bridge.py`：面向前端的 session handle（BridgeSession），封装 send_message、iter_events、async_wait_for_reply。
- `env.py`：`.env` 文件加载工具。
- `cap.py`：资源/上下文裁剪辅助逻辑。
- `git_coordinator.py`：session 间 git 协调，处理 master claim 与 checkpoint。

## 与其他模块的依赖关系
- 调用 `session_engine`：watcher 创建 Session、读写 status/params、检查 entity alignment。
- 调用 `llm_engine`：watcher 中 resolve_provider 构建 agent。
- 被 `ui/` 调用：CLI/Web 通过 bridge、ipc 操纵 session。
