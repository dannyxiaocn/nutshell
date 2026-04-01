# Nutshell ← Claude Code Insights

基于对 Claude Code 源码（`claude-code-main/src/`，~1800 文件）的深度分析，提炼出对 nutshell 有价值的设计洞察。

由 6 个并行 Explore Agent 团队完成，分析日期：2026-04-01。

---

## 文件目录

| 文件 | 主题 | 关键发现 |
|------|------|---------|
| [01-multi-agent-architecture.md](01-multi-agent-architecture.md) | Multi-Agent、Task 系统、Swarm | 三层执行模式、文件邮箱、GitCoordinator |
| [02-permission-system.md](02-permission-system.md) | 权限系统、沙箱、Plan Mode | 5种权限模式、20+安全检查、Worktree隔离 |
| [03-cli-commands-dx.md](03-cli-commands-dx.md) | CLI 命令、调试工具、DX | doctor、rewind、ultrareview、REPL工具 |
| [04-memory-system.md](04-memory-system.md) | 记忆系统、上下文压缩 | extractMemories、SessionMemory、autocompact |
| [05-prompt-engineering.md](05-prompt-engineering.md) | Prompt 工程、缓存策略 | BOUNDARY标记、全局缓存、autoDream |
| [06-skills-plugins-mcp.md](06-skills-plugins-mcp.md) | Skills、插件、MCP | 延迟加载、参数替换、路径过滤 |

---

## 高优先级改进（可立即实施）

### 🔴 P0 - 核心架构

**1. Plan Mode（只读探索模式）**
- 来源：`02-permission-system.md`
- CC 设计：EnterPlanMode 切换到只读模式，编辑工具自动拒绝，ExitPlanMode 恢复
- nutshell 实现：添加 `PermissionMode.PLAN`，在 `BashExecutor.check_permission()` 中检查
- **价值**：让 agent 先制定计划再执行，避免盲目写代码

**2. Fail-closed 工具接口**
- 来源：`02-permission-system.md`
- CC 设计：`isConcurrencySafe` 默认 false，`isReadOnly` 默认 false
- nutshell 实现：Tool ABC 添加 `is_read_only()` 和 `is_concurrency_safe()`，默认返回 False
- **价值**：要求工具主动声明安全性，而非假设安全

**3. Skill 参数替换**
- 来源：`06-skills-plugins-mcp.md`
- CC 设计：SKILL.md 支持 `{file_path}` 占位符
- nutshell 实现：在 `skill_engine/renderer.py` 中添加参数替换
- **价值**：技能可接受动态参数，表达能力大幅提升

**4. MEMORY.md 大小限制**
- 来源：`04-memory-system.md`
- CC 设计：200 行 / 25KB 限制，超限截断并警告
- nutshell 实现：在 `_build_system_prompt()` 中检查 memory.md 大小
- **价值**：防止 memory 文件过大撑爆 context window

### 🟡 P1 - 重要改进

**5. 前端优先的异步任务框架**
- 来源：`01-multi-agent-architecture.md`
- CC 设计：任务立即注册到 AppState，后台异步执行，通过 `<task-notification>` 推送完成
- nutshell 实现：`spawn_session` 立即返回 task_id，后台运行，events.jsonl 推送进度
- **价值**：用户不被阻塞，立即看到进度

**6. 工具延迟加载（shouldDefer + ToolSearch）**
- 来源：`06-skills-plugins-mcp.md`
- CC 设计：MCP 工具默认不进入初始 prompt，通过 ToolSearchTool 按需激活
- nutshell 实现：`@register_tool(deferred=True)` + `tool_search` 工具
- **价值**：大量工具时减少 prompt 大小，不影响可用性

**7. SYSTEM_PROMPT_DYNAMIC_BOUNDARY 标记**
- 来源：`05-prompt-engineering.md`
- CC 设计：BOUNDARY 标记前的内容使用全局 cache_control scope，跨会话重用
- nutshell 实现：在 `_build_system_parts()` 返回三段，前段用 `scope: "global"`
- **价值**：显著降低 API 成本（全局缓存命中率更高）

**8. Skill Token 预算约束**
- 来源：`06-skills-plugins-mcp.md`
- CC 设计：技能目录总 token ≤ 上下文的 1%，每条 ≤ 250 字符
- nutshell 实现：在 `build_skills_block()` 中添加预算约束
- **价值**：防止技能过多时 prompt 膨胀

**9. 增强 Bash 安全检查**
- 来源：`02-permission-system.md`
- CC 设计：20+ 种检查（Zsh危险命令、进程替换、Unicode空白等）
- nutshell 实现：在 `BashExecutor` 中添加 `ZSH_DANGEROUS_COMMANDS`、进程替换检测
- **价值**：防御更多 shell 注入向量

**10. 会话分支（Branch）**
- 来源：`03-cli-commands-dx.md`
- CC 设计：从当前会话创建独立分支，保留 parentUuid 链
- nutshell 实现：`nutshell branch [name]`，复制 context.jsonl 到新 session ID
- **价值**：支持探索性对话而不破坏主线

### 🟢 P2 - 长期改进

**11. autoDream（跨会话内存整理）**
- 来源：`04-memory-system.md` + `05-prompt-engineering.md`
- CC 设计：三重门闩（24h + 5个会话 + 节流），后台 forked agent 整理 memory
- **价值**：长期使用时 memory 不会退化

**12. Session Memory 自动提取**
- 来源：`04-memory-system.md`
- CC 设计：每 5k tokens 或 3 次工具调用后自动提取会话摘要
- **价值**：压缩前保留重要信息，减少 compact 损失

**13. 智能诊断命令（doctor）**
- 来源：`03-cli-commands-dx.md`
- CC 设计：检查版本、配置、agent 文件、环境变量、插件等
- nutshell 实现：`nutshell doctor` 检查 sessions/、env、entity 配置等

**14. Worktree 隔离**
- 来源：`02-permission-system.md`
- CC 设计：创建 git worktree + 切换 session CWD，完全文件系统隔离
- **价值**：探索性开发不污染主分支

**15. 多执行后端抽象（Swarm）**
- 来源：`01-multi-agent-architecture.md`
- CC 设计：PaneBackend 接口 + InProcess/Tmux/iTerm2 三种后端
- **价值**：支持同进程轻量隔离，减少进程开销

---

## nutshell 相对于 CC 的优势（可保留）

| nutshell 特有设计 | 优势 |
|-----------------|------|
| **实体级记忆种子**（entity/memory/） | 跨会话的项目级模板，CC 只有用户级记忆 |
| **Meta-session 机制** | entity 级可变状态，CC 无对应设计 |
| **recall_memory 按需检索** | 不全量注入，memory 大时更高效 |
| **文件 IPC（context.jsonl）** | 纯文件无依赖，CC 用内存+文件混合 |
| **Gene 特性** | meta session 初始化命令，CC 无对应 |
| **简洁的 entity 系统** | 对比 CC 的复杂 AgentDefinition，更易理解 |

---

## 架构差异总结

```
Claude Code（TypeScript + React/Ink）      Nutshell（Python + FastAPI）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AppState（内存中心状态）               → sessions/<id>/ 文件中心状态
AsyncLocalStorage 同进程隔离           → 进程隔离（更重但更简单）
5种权限模式 + AI分类器                 → DANGEROUS_DEFAULTS + blocked_patterns
SYSTEM_PROMPT_DYNAMIC_BOUNDARY         → _build_system_parts() 两段
ToolSearch 延迟加载                    → 全量注入工具
autoDream 后台整理                     → 无
extractMemories hook                   → 手动更新
Plugin 系统 + marketplace              → entity/skills/ 目录
MCP 标准集成                           → 无
```
