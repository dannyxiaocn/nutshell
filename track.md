# Nutshell Track

> 驱动开发看板。实现类任务必须派发给 `nutshell_dev_codex`，Claude Code 只做维护类操作。  
> 每次完成一个任务后：更新 track.md（标记[x] + commit ID）、MEMORY.md、README.md，检查遗留代码。

---

## Module 0 · DEBUG（快速修）

- [ ] **harness.md 模型字段错误**：`session.py:658` `self._agent.model` 写入的是 agent.yaml 里的 model 字符串（如 `openai-codex/gpt-5.4`），但有些 session 里 model 不一致（例如同一 entity 出现 `gpt-5.4` 和 `openai-codex/gpt-5.4` 两种写法）。需要 provider 在 `complete()` 后回填实际 model ID，或者从 provider 读取 `actual_model`，写入 harness 时加 `provider` 字段一并显示。

---

## Module 1 · CLI 清理

- [ ] **删除遗留 `nutshell chat` 旧接口和 dui 系列命令**：检查 `ui/cli/main.py` 内所有 `@app.command` / subcommand，找出已废弃的 chat 旧入口和其他 dui 遗留（如早期对话模式）。列出后整体删除，确保新的 chat.py 路径干净。
- [ ] **CLI 接口审计**：梳理所有 CLI 命令，删除功能重叠或已废弃的 sub-command，保持接口最小化。

---

## Module 2 · Multi-agent 通信 & QJBQ 融合 + Cambridge Agent Protocol

- [ ] **QJBQ 移到 `cli_app/`**：当前 `qjbq/` 在 repo root，统一 agent app 放置规范，迁移到 `cli_app/qjbq/`（或明确目录命名），更新所有 import 和文档引用。
- [ ] **删除系统自带通信方式，统一用 QJBQ**：`tool_engine/providers/session_msg.py` 的 `send_to_session` 是系统级通信，评估是否可用 QJBQ 替换或作为 QJBQ 底层；删除重复路径，只保留一条 agent 间通信的 canonical 路径。
- [ ] **Cambridge Agent Protocol (CAP) 模块设计**：  
  - agent 主动发起的交互 = **app**（如 qjbq、spawn_session）  
  - 被动系统监管的交互 = **protocol**（CAP 层）  
  - `git_coordinator` 归入 CAP —— 这是 multi-agent protocol 隔离层，类似 Python 的 GIL  
  - 设计 CAP 接口（`nutshell/runtime/cap.py`）：定义 agent 可参与的协议原语（handshake、lock、broadcast、heartbeat-sync）  
  - git_coordinator 作为 CAP 的第一个 protocol 实现

---

## Module 3 · Meta-session 完善

- [ ] **整理现有 entity**：审查 `entity/` 下所有 entity（agent, cli_os, game_player, kimi_agent, nutshell_dev, nutshell_dev_codex, openai_agent, persistent_agent, receptionist, yisebi），归档或删除无用的，补全缺少描述/用途不明的。
- [ ] **meta session 作为 entity 实例化单位**：确认 `sessions/<entity>_meta/` 完整继承 memory + playground；补全对应文档和 agent.yaml 里的说明字段。
- [ ] **给 meta session 配工具：子 session 管理**：  
  - `list_child_sessions(entity)` — 列出 entity 所有子 session + status  
  - `get_session_info(session_id)` — 获取 session manifest + 最近 turns + tasks  
  - `archive_session(session_id)` — 将 session 移到 `_archived/` 而非删除  
  - dream 机制：meta session 定期（24h）审查子 session，决定 keep / archive
- [ ] **Bridge 子进程标注 + Persistent agent 标识**：  
  - 已 link 到 bridge 的子进程：状态显示 `napping`（嫩绿色灯），而非普通 idle  
  - persistent agent（`params.json` 里 `persistent: true`）：单独颜色/图标，表示一直在运行  
  - 在 `nutshell friends` 和 web UI 中体现
- [ ] **分层 memory 调整（单向流）**：  
  - 方向：`entity/ → meta session → child sessions`（单向下流）  
  - **删除** child 主动更新 meta 的接口（`update_meta_memory` tool 删除或改为仅 meta session 自用）  
  - agent prompt 中明确告知此架构  
  - 原则：最小化系统，之后有需求再添加

---

## Module 4 · Entity 继承系统改进

- [ ] **meta session 完备，entity 保留继承标识**：  
  - meta session 展开后完全看不到继承关系（扁平化），对 agent 透明  
  - entity 定义里保留标识：`link`（指向 parent）、`own`（自己独有）、`append`（在 parent 基础上追加）  
  - meta session 的「自己部分」完全独立，entity 更新只更新继承的部分  
- [ ] **entity 可更新 parent entity 内容**：设计 `propose_parent_update` 接口（已有 `propose_entity_update`），支持更新 parent entity 的继承内容，走 review 流程

---

## Module 5 · Thinking 配置

- [ ] **enable thinking 作为可配置项**：在 `params.json` 增加 `thinking: true/false`（及 `thinking_budget`），AnthropicProvider 读取后在 `complete()` 时启用 extended thinking；OpenAI provider 类似。同步更新 session.py 参数加载逻辑。

---

## Module 6 · 安全审查 / Sandbox 重设计

- [ ] **Tool-level sandbox 重设计**（参考 claude code tool sandbox）：  
  - 当前 sandbox 是 bash 命令级别（`BashExecutor` 过滤危险命令）  
  - 新设计：每个 tool 有独立 sandbox policy（pre-check + post-filter），agent 不可见 sandbox 逻辑，只看 tool 返回  
  - 跳出 playground 修改系统文件：在 bash tool sandbox 里加 path scope 限制  
  - 设计 `nutshell/tool_engine/sandbox.py`：`ToolSandbox` 基类，`BashSandbox` / `WebSandbox` / `FSSandbox` 实现

---

## Module 7 · 工具 Stats 系统

- [ ] **Harness 分层命名**：  
  - `harness`（保留）= agent 自我感知组件的总称  
  - 拆分为：`sys_harness`（系统基础，每 turn 自动写）+ `audit_harness`（工具/skill 使用审计，跨 session 聚合）  
  - 读读 harness 相关 blog，明确定义边界
- [ ] **Token 计算器 tool**：`count_tokens(text, model)` built-in tool，调用 tokenizer 精确计算 token 数，供 agent 在操作前评估 cost。
- [ ] **Tool manager persistent agent**：专职维护 tool stats，定期聚合 harness 数据，输出 tool 使用热力图 + 效率报告到 `_sessions/tool_stats/`。
- [ ] **Nutshell 专职 persistent agent 体系**：  
  - `dev_maintainer` — 保证无 bug + 最精简化每个功能（基于 nutshell_dev）  
  - `tool_craftsman` — 不断迭代打磨 tool/skill 质量  
  - 历史 audit 数据保留在 `_sessions/<entity>_meta/core/audit/`，与 meta session dream 频次 align  
  - **与 meta session 协调**：meta session「删除」子 session 时移到 `archived/`，audit 数据不丢失

---

## 完成记录

<!-- 格式：- [x] 任务名 (commit: abc1234) -->
