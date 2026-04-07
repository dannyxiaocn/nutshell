# entity

一句话定位：存放 nutshell 内置 agent 实体模板；每个子目录定义一种可实例化的 agent 配置单元。

## 文件/子目录列表
- `README.md`：当前目录总览。
- `agent/`：默认通用 agent；定义基础 prompts、工具与技能集合，是多数实体的继承基类。
- `cli_os/`：偏 shell/CLI 操作的专用实体。
- `dev_maintainer/`：持续关注测试、代码质量与维护任务的实体。
- `game_player/`：游戏/谜题求解导向实体。
- `kimi_agent/`：Kimi provider 变体，复用默认 agent 能力面。
- `nutshell_dev/`：用于开发 nutshell 仓库本身的实体，附带项目技能与 heartbeat。
- `nutshell_dev_codex/`：`nutshell_dev` 的 Codex/OpenAI 变体，带专用 memory 模板。
- `openai_agent/`：OpenAI provider 变体。
- `persistent_agent/`：长心跳、持久在线的通用后台实体。
- `receptionist/`：对外接口/任务分发实体。
- `tool_craftsman/`：聚焦工具与技能打磨的维护实体。
- `tool_manager/`：聚合审计日志并分析工具使用情况的后台实体。
- `yisebi/`：面向社交评论场景的风格化实体。

各实体目录通常包含：
- `agent.yaml`：实体定义，声明继承、prompts、tools、skills、params、meta_session 等。
- `prompts/`：system / heartbeat / session prompt 文件。
- `tools/`：该实体默认暴露的工具 schema。
- `skills/`：该实体默认挂载的技能。
- `memory.md` / `memory/*.md`：实体级共享记忆模板。
- `playground/`：可下沉到 meta session 的共享可变工作区种子。
- `README.md`：该实体自身说明。

## 关键设计 / 架构说明
- entity 是模板层，不是运行中的 session；真正执行前会被 runtime 扁平化并复制到 `sessions/` / `_sessions/`。
- 通过 `extends` 形成继承树，支持 links / append / own 等继承策略，由 `runtime/agent_loader.py` 处理。
- `meta_session` 用于把 entity 的共享可变状态提升为实体实例层：后续子 session 可继承已经演化过的 memory/playground。
- tools/skills/prompts 均以文件系统为事实来源，便于热更新、审阅和版本控制。
- provider/model 只是实体配置的一部分，因此同一行为模板可以做多个 provider 变体。

## 主要对外接口
本目录本身不提供 Python API，主要暴露给 runtime 的文件接口：

### `agent.yaml`
示例：
```yaml
name: receptionist
extends: agent
model: claude-sonnet-4-6
provider: anthropic
prompts:
  system: prompts/system.md
tools:
  - tools/bash.json
```
被 `nutshell.runtime.agent_loader` / `session_factory` 读取并实例化。

### 目录级能力声明
- `prompts/*.md`：被复制到 session `core/`。
- `tools/*.json`：被 `ToolLoader` 加载。
- `skills/*/SKILL.md`：被 `SkillLoader` 加载。
- `memory*.md`：被 session 注入到 prompt memory 层。

## 与其他模块的依赖关系
- 被 `nutshell.runtime.agent_loader`、`session_factory`、`meta_session` 直接消费。
- 间接驱动 `nutshell.core.Agent` 的 prompts/tools/skills/memory 组合方式。
- 与 `ui/` 交互：CLI/Web 创建新 session 时本质上是在选择某个 entity。
- 测试覆盖位于 `tests/test_entity_*`、`tests/runtime/test_meta_session.py` 等。
