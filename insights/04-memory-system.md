# Claude Code 记忆系统与上下文管理 — 深度分析

## 执行摘要

Claude Code 的记忆系统是一个**多层级、自动化、缓存友好**的架构：
- **extractMemories**：持续捕捉背景工作流中的隐性知识
- **SessionMemory**：为压缩做准备，避免压缩中的重复分析
- **Compact**：保留精确的技术细节，优先用户反馈
- **Memdir**：文件系统持久化 + 自动相关性筛选

---

## 一、extractMemories 服务工作原理

### 何时触发
- 在每个完整查询循环结束时触发（模型产生最终响应且无工具调用时）
- 通过 `handleStopHooks` 在 `stopHooks.ts` 中调用
- 可配置节流：默认每1个符合条件的回合执行一次（`tengu_bramble_lintel` 特性门控）
- **仅在主agent中执行，不在子agent中执行**

### 提取什么
- 分析最近 `~N` 条消息（统计自上次提取后的所有模型可见消息）
- 遵循四类记忆分类法：
  - `User`（用户信息、角色、偏好）
  - `Feedback`（反馈和纠正）
  - `Project`（项目状态、决策）
  - `Reference`（外部资源指针）
- **排除可衍生内容**：代码模式、架构、git历史等
- 通过 forked agent 模式运行，共享父对话的提示缓存

### 写到哪里
- `~/.claude/projects/<path>/memory/` 目录中的单独文件
- 每个记忆一个文件（如 `user_role.md`、`feedback_testing.md`）
- 更新 `MEMORY.md` 索引文件（一行一个指针，<150字符）
- 支持 team memory 时写到 `memory/team/` 子目录

### 核心防护机制
```
状态管理（闭包作用域）：
├── lastMemoryMessageUuid    ← 游标，仅处理新消息
├── inFlightExtractions      ← 追踪所有未完成提取
├── inProgress               ← 防止重叠运行的标志
├── turnsSinceLastExtraction ← 节流计数器
└── pendingContext          ← 合并重叠调用到尾部运行

防护机制：
├── 互斥排除：主agent已写入记忆 → 跳过forked agent
├── 工具限制：仅允许Read/Grep/Glob + 只读Bash + Edit/Write限于memory/
├── 回合预算：maxTurns=5，防止验证兔子洞
└── 缓存分析：logEvent记录缓存命中率、生成token等
```

---

## 二、SessionMemory 数据结构与管理方式

### 数据结构
```typescript
SessionMemoryConfig {
  minimumMessageTokensToInit: number      // 初始化阈值 (default: 10k tokens)
  minimumTokensBetweenUpdate: number      // 更新间隔 (default: 5k tokens)
  toolCallsBetweenUpdates: number         // 工具调用阈值 (default: 3 calls)
}

State (sessionMemoryUtils.ts):
├── lastSummarizedMessageId              ← 追踪已总结范围
├── extractionStartedAt                  ← 防止重叠提取的时间戳
├── tokensAtLastExtraction               ← 上次提取的context大小
└── sessionMemoryInitialized             ← 已超过初始化阈值？
```

### 文件位置
- `~/.claude/sessions/<session-id>/memory.md` — 当前会话摘要
- 使用 FileEdit 工具原子更新

### 触发逻辑
```
shouldExtractMemory() {
  1. 检查token初始化阈值：
     tokenCountWithEstimation(messages) >= minimumMessageTokensToInit
     → 首次达到时标记已初始化
  
  2. 检查更新阈值（两个条件之一）：
     ├── (token增量 >= 5k) AND (tool calls >= 3) 
     └── (token增量 >= 5k) AND (最后一个assistant回合无tool call)
}
```

**特点**：
- 后台运行通过 `sequential()` 队列确保顺序性
- 使用 runForkedAgent + createCacheSafeParams 共享提示缓存
- 与自动压缩集成：auto-compact 启用时才初始化

---

## 三、Compact（上下文压缩）实现

### 何时触发
- **自动**：context tokens 达到阈值时
  ```
  autocompact_threshold = effective_context_window - AUTOCOMPACT_BUFFER_TOKENS(13k)
  ```
- **手动**：用户通过 `/compact` 命令触发
- **预检警告**：75% context → warning；95% → error

### 压缩策略与重要信息保留

**消息分组（grouping.ts）**：
- 按 API 回合分组（同一回合的 assistant + tool_result 视为单元）
- 部分压缩时保留原始消息边界

**摘要生成（prompt.ts）**：
```
NO_TOOLS_PREAMBLE (强制文本输出)
↓
DETAILED_ANALYSIS_INSTRUCTION
├── 逐条分析每条消息
├── 用户意图识别
├── 技术决策/代码模式
├── 具体文件名、代码片段、函数签名
├── 错误与修复方案
└── 用户反馈优先处理
↓
结构化总结（9个部分）：
1. Primary Request and Intent
2. Key Technical Concepts
3. Files and Code Sections (with full snippets!)
4. Errors and fixes
5. Problem Solving
6. All user messages (non-tool-result)
7. Pending Tasks
8. Current Work (最新工作详情)
9. Optional Next Step (直接引用用户要求原文)
```

**缓存和资源恢复（postCompactCleanup.ts）**：
- 恢复最多 5 个最常访问的文件（`POST_COMPACT_MAX_FILES_TO_RESTORE=5`）
- 预算：50k token 总额
- 每个文件最多 5k token，每个 skill 最多 5k token
- 这样可以继续快速访问最近工作的代码

**保留重要信息的关键技术**：
- 分析块 `<analysis>` 用于推理，摘要前移除（保持摘要简洁）
- 强制要求具体文件名、完整代码片段、函数签名
- 优先级：用户反馈 > 错误修复 > 技术决策 > 一般讨论
- 下一步指导：必须直接引用用户最新请求的原文

---

## 四、Memdir 机制（内存目录系统）

**位置**：`~/.claude/projects/<slug>/memory/`

### 核心组件

**MEMORY.md（索引文件）**：
- 最多 200 行，25KB 字节限制
- 每行一个指针：`- [Title](file.md) — one-line hook`
- 始终加载到 system prompt
- 超限时自动截断并警告

**记忆文件结构**：
```yaml
---
name: "Memory Title"
description: "Concise description"
type: "User|Project|Feedback|Reference"
---

Content here...
```

**记忆扫描（memoryScan.ts）**：
- 前置读取 MEMORY.md frontmatter
- 返回文件名、描述、更新时间等元数据
- 避免模型浪费回合做 `ls`

**相关性检索（findRelevantMemories.ts）**：
- 用 Sonnet 选择最多 5 个相关记忆
- 排除已在对话中展示的（不浪费 token）
- 过滤掉最近使用工具的参考文档（降噪）

**Team memory 支持**（可选，TEAMMEM 特性门控）：
- `memory/team/` 子目录存储共享记忆
- 提取时明确说明避免保存敏感数据

---

## 五、会话历史（sessionHistory.ts）数据结构

```typescript
HistoryPage {
  events: SDKMessage[]              // 按时间顺序排列
  firstId: string | null            // 该页最旧事件的ID（before_id游标）
  hasMore: boolean                  // 是否存在更旧的事件
}
```

**设计模式**：
- **分页游标模式**：`anchor_to_latest` 获取最新页，`before_id` 获取更旧页
- **认证复用**：一次创建 `HistoryAuthCtx`，多次分页调用重用
- sessionHistory 是 API 级别原始事件日志，sessionMemory 是应用层摘要
- compact 使用 sessionMemory 总结，而非重新遍历历史

---

## 六、对 Nutshell 的改进建议

### 对比分析

| 方面 | Claude Code | Nutshell 当前 | 建议改进 |
|------|------------|-------------|--------|
| 记忆文件结构 | Frontmatter + content | 纯 markdown | 添加 frontmatter (name/description/type) |
| 索引MEMORY.md | 200行/25KB 限制 + 截断警告 | 无限制 | 实现截断 + 警告机制 |
| 相关性检索 | Sonnet 选择（最多5个） | recall_memory substring 搜索 | 添加 LLM 辅助的相关性检索 |
| 提取触发 | token阈值 + 工具调用阈值 | 完全手动 | 阈值驱动的自动提取 hook |
| 压缩整合 | autocompact 前先提取 sessionMemory | 无 | 长会话压缩前自动生成摘要文件 |

### 具体建议

**P0 - 引入 Frontmatter 规范**：
```yaml
# sessions/<id>/core/memory/work_state.md
---
name: "Work State"
description: "Current task, commit progress, next steps"
type: "Project"
---

## Current Task
...
```
在 session 激活时解析元数据，支持按 type 过滤。

**P1 - MEMORY.md 大小限制**：
```python
# 实现与 Claude Code 相同的限制
MAX_MEMORY_LINES = 200
MAX_MEMORY_BYTES = 25 * 1024  # 25KB

def check_memory_health(memory_path):
    with open(memory_path) as f:
        content = f.read()
    lines = content.splitlines()
    if len(lines) > MAX_MEMORY_LINES:
        warn(f"MEMORY.md 超过 {MAX_MEMORY_LINES} 行，将被截断")
```

**P1 - 自动会话摘要提取（基于 token 阈值）**：
```python
# 在 session.py 的 chat() 中
async def maybe_extract_session_memory(self):
    """每 5k tokens 或 3 次工具调用后自动提取记忆"""
    if self._should_extract_memory():
        asyncio.create_task(self._extract_memory_background())

async def _extract_memory_background(self):
    """后台运行，不阻塞主对话"""
    summary = await self._generate_session_summary()
    self._write_memory_file("session_summary.md", summary)
```

**P1 - 压缩（Compact）命令**：
```python
# nutshell compact [session-id]
# 1. 先生成会话摘要
# 2. 保留最近 N 条消息
# 3. 替换历史为摘要
# 4. 恢复最常访问文件的内容
```

**P2 - LLM 辅助相关性检索**：
```python
# 当前 recall_memory 是 substring 搜索
# 可升级为：给定当前对话上下文，让 LLM 选择最相关的 memory 文件（最多5个）
async def find_relevant_memories(query: str, memory_dir: Path) -> list[Path]:
    all_memories = scan_memory_files(memory_dir)  # 读取 frontmatter 元数据
    return await llm_select_relevant(query, all_memories, max=5)
```

### Nutshell 特有优势（可反向输出给 CC）

- **实体级记忆种子**（跨会话重用）：Claude Code 仅有用户记忆，无项目级模板
- **灵活的 recall_memory**（按需查询）：Claude Code 全量注入，memory 过大时低效
- **Meta-session 机制**：entity 级别可变状态，CC 没有对应的设计

---

## 关键设计原则

1. **自动化而非手动**：提取和摘要在后台自动触发，不依赖 agent 主动调用
2. **游标追踪**：用 `lastMemoryMessageUuid` 确保只处理新消息，防止重复
3. **缓存友好**：forked agent 共享父 agent 的 prompt cache，几乎不增加成本
4. **优先级明确**：用户反馈 > 错误修复 > 技术决策 > 一般讨论
5. **工具权限限制**：提取 agent 的工具受严格限制（只读 + 仅写 memory/）
6. **防止重叠**：互斥标志 + 尾部合并，防止并发提取导致冲突
