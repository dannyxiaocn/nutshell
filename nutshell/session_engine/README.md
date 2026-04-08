# nutshell/session_engine

Session 生命周期管理 + entity 资产的 session 化。

Entity 是 agent 的模板配置（只读），session_engine 负责把 entity 实例化为可运行的 session，并管理 session 的整个生命周期。

## 文件列表

### Session 生命周期
- `session.py`：`Session` 主体；chat()、tick()、run_daemon_loop()，从 core/ 热加载 prompts/tools/skills。
- `session_init.py`：`init_session()` — 从 entity 创建 session 目录结构，复制 prompts/tools/skills/memory。
- `session_status.py`：`status.json` 读写、pid 存活检测。
- `session_params.py`：`params.json` 读写；DEFAULT_PARAMS 定义（model、provider、session_type 等）。

### Entity 资产管理
- `entity_config.py`：`AgentConfig` — 解析 agent.yaml，处理 entity 继承链（extends）。
- `entity_state.py`：Meta session 管理 — entity→meta 同步、对齐检查、gene 命令执行、meta agent 启动。
- `agent_loader.py`：`AgentLoader` — 从 entity 目录构建完整 Agent（协调 ToolLoader + SkillLoader + LLM provider）。

## Entity → Session 链路

```
entity/<name>/          只读配置模板
    ↓ populate_meta_from_entity()
sessions/<name>_meta/   entity 级可变状态（共享 memory、playground）
    ↓ init_session()
sessions/<id>/          具体 session 实例
    ↓ Session(agent)
运行中的 agent          热加载 core/ 内容，heartbeat 驱动
```

## 与其他模块的依赖关系
- 依赖 `core`：Agent、Tool、Skill、Provider ABC、Hook 类型。
- 依赖 `llm_engine`：resolve_provider 构建 provider 实例。
- 依赖 `tool_engine` / `skill_engine`：AgentLoader 和 Session 从 core/ 加载 tools/skills。
- 被 `runtime` 调用：watcher 创建 Session 并驱动 run_daemon_loop。
- 被 `ui/` 调用：CLI/Web 通过 session_init、session_status、session_params 操纵 session。
