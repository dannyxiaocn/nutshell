# Claude Code Multi-Agent 架构深度分析

## 执行摘要

Claude Code 采用**分层式多 Agent 架构**，核心设计优势为：

1. **三层 Agent 执行模式**：LocalAgentTask（后台本地）、RemoteAgentTask（云端）、InProcessTeammateTask（同进程隔离）
2. **抽象化后端（Swarm）**：支持 Tmux、iTerm2、In-Process 三种执行后端，可无缝切换
3. **异步任务框架**：统一的任务生命周期管理，与 AppState 集成，支持进度跟踪和通知
4. **权限和隔离**：每个 Agent 有独立的权限模型、消息邮箱、AsyncLocalStorage 上下文隔离
5. **Fork 子 Agent**：轻量级派生机制，子 Agent 继承父 Agent 的完整对话上下文，实现快速并发

---

## 一、AgentTool 架构

### 1.1 AgentTool 的设计目标

AgentTool 是 Claude Code 中生成 Agent 的核心工具。与 nutshell 的 `spawn_session` 不同，Claude Code 采用**前端优先、后端无关**的设计：

- **前端创建 Task**：AgentTool 调用立即在 AppState 中注册 LocalAgentTask，用户看到 loading 状态
- **后端异步执行**：Agent 在后台运行（通过 runAgent generator），无需等待前端同步
- **结果通知**：Agent 完成时通过消息队列推送 `<task-notification>`，触发模型的下一轮对话

```typescript
// LocalAgentTask 状态（AppState 中持久化）
type LocalAgentTaskState = TaskStateBase & {
  type: 'local_agent'
  agentId: string
  prompt: string
  selectedAgent?: AgentDefinition
  agentType: string
  abortController?: AbortController
  error?: string
  result?: AgentToolResult
  progress?: AgentProgress  // 实时进度追踪
  messages?: Message[]       // 完整对话历史（用于 UI 显示）
  pendingMessages: string[]  // 中途接收的用户消息
  isBackgrounded: boolean    // 任务是否后台化
  retain: boolean            // UI 是否持有（防止 GC）
  evictAfter?: number        // GC 优雅期
}
```

### 1.2 Agent 定义和类型

Claude Code 支持三种 Agent 定义方式：

**内置 Agent** (`source: 'built-in'`)
- `generalPurposeAgent`：通用工作者
- `planAgent`：规划和决策
- `exploreAgent`：代码探索
- `verificationAgent`：测试验证
- `claudeCodeGuideAgent`：指导文档

**自定义 Agent** (`source: 'file'` 或 `source: 'plugin'`)
- 项目的 `.claude/agents/` 中的 YAML/Markdown 定义
- 支持 Frontmatter 配置：tools、model、permissionMode、mcpServers 等

**Fork Agent** (隐式派生，实验特性)
- 省略 `subagent_type` 时触发，子 Agent 继承父 Agent 的全部对话上下文
- 用于快速并发任务分解

```typescript
type AgentDefinition = {
  agentType: string
  whenToUse: string
  tools: string[]  // ['*'] 表示通配符，支持权限规则如 'Bash:grep'
  model?: string   // 'inherit' 表示继承父 Agent 的模型
  permissionMode?: 'default' | 'plan' | 'bubble'  // 权限行为
  maxTurns?: number
  mcpServers?: (string | Record<string, MCPConfig>)[]  // Agent 专属 MCP
  source: 'built-in' | 'file' | 'plugin'
  disallowedTools?: string[]  // 禁止工具列表
}
```

### 1.3 Agent Memory Snapshot 机制

Agent Memory 允许 Agent 跨会话保存学习，有三个范围级别：

```typescript
type AgentMemoryScope = 'user' | 'project' | 'local'

// 范围对应的目录：
// 'user':    ~/.claude/agent-memory/<agentType>/
// 'project': <cwd>/.claude/agent-memory/<agentType>/
// 'local':   <cwd>/.claude/agent-memory-local/<agentType>/  (不入版本控制)
```

**Snapshot 工作流**：
1. **初始化阶段**：Agent 启动时检查 snapshot.json 是否存在且比本地内存新
2. **同步策略**：
   - `action: 'none'` - 跳过
   - `action: 'initialize'` - 从 snapshot 首次复制到本地（无本地记录时）
   - `action: 'prompt-update'` - Prompt 注入 snapshot 内容提醒 Agent 更新已知内容

```typescript
export async function checkAgentMemorySnapshot(
  agentType: string,
  scope: AgentMemoryScope,
): Promise<{
  action: 'none' | 'initialize' | 'prompt-update'
  snapshotTimestamp?: string
}>
```

**用途**：
- 项目级共享记忆：整个团队的 Agent 可共享 .claude/agent-memory/ 中的知识
- 用户级通用记忆：跨项目的 Agent 学习保存在 ~/.claude/agent-memory/

---

## 二、Task 类型系统

Claude Code 的任务系统是**统一的后台任务框架**，每个 Agent 执行对应一个 Task。

### 2.1 Task 类型分类

```typescript
type TaskState =
  | LocalShellTaskState       // 本地 Shell 命令
  | LocalAgentTaskState       // 本地后台 Agent
  | RemoteAgentTaskState      // 云端 Agent（Teleport）
  | InProcessTeammateTaskState // 同进程队友 Agent
  | LocalWorkflowTaskState     // 工作流
  | MonitorMcpTaskState        // MCP 监控
  | DreamTaskState             // 自动梦想（内存巩固）
```

### 2.2 LocalAgentTask - 后台本地执行

**执行模式**：
- Agent 在主线程的异步 generator 中运行（`runAgent()`）
- 每个 turn 的消息和工具使用通过 `updateProgressFromMessage()` 追踪
- Task 完成或失败时自动推送 `<task-notification>`

**关键特性**：
```typescript
// 进度追踪
type ProgressTracker = {
  toolUseCount: number
  latestInputTokens: number        // 最新输入（累积）
  cumulativeOutputTokens: number   // 累积输出
  recentActivities: ToolActivity[] // 最近 5 个工具调用
}

// Agent 通知格式
<task-notification>
  <task-id>xxx</task-id>
  <status>completed|failed|killed</status>
  <summary>Agent "name" completed</summary>
  <result>Final text output</result>
  <usage>
    <total_tokens>N</total_tokens>
    <tool_uses>N</tool_uses>
    <duration_ms>N</duration_ms>
  </usage>
</task-notification>
```

**生命周期**：
1. `registerTask()` - 注册到 AppState
2. `runAgent()` - 执行 generator
3. `updateAgentProgress()` - 实时进度更新
4. `enqueueAgentNotification()` - 完成时推送通知
5. `evictTaskOutput()` - GC 阶段回收文件

### 2.3 RemoteAgentTask - 云端执行（Teleport）

**用途**：长期运行的后台任务，如 PR review、autofix 等

**执行流程**：
```typescript
type RemoteAgentTaskState = TaskStateBase & {
  remoteTaskType: 'remote-agent' | 'ultraplan' | 'ultrareview' | 'autofix-pr' | 'background-pr'
  sessionId: string              // Teleport 远程会话 ID
  pollStartedAt: number          // 轮询开始时间
  command: string                // 启动命令
  todoList: TodoList             // 远程会话中提取的任务列表
  log: SDKMessage[]              // 远程会话消息日志
  reviewProgress?: {             // 仅用于 ultrareview
    stage: 'finding' | 'verifying' | 'synthesizing'
    bugsFound: number
    bugsVerified: number
  }
}
```

**轮询机制**：
- `registerCompletionChecker()` - 注册特定任务类型的完成检查回调
- 后台定时轮询远程会话，检查完成条件
- 完成后从远程会话提取结果（plan、review、todo list）
- 通知主会话继续对话

### 2.4 DreamTask - 自动内存巩固

**背景**：Claude Code 持续记录所有 Agent 对话到本地文件，长期会累积大量对话。DreamTask 是一个**自动触发的子 Agent**，定期汇总和优化已有的对话记录。

```typescript
type DreamTaskState = TaskStateBase & {
  type: 'dream'
  phase: 'starting' | 'updating'
  sessionsReviewing: number
  filesTouched: string[]        // 记忆巩固过程中修改的文件
  turns: DreamTurn[]            // 梦想 Agent 的轮次（文本 + 工具计数）
}
```

**工作流**：
1. 锁定巩固过程（防止并发修改）
2. 启动一个隐式 fork 子 Agent 读取并汇总旧对话
3. 子 Agent 修改内存文件（Edit/Write 工具）
4. 完成后解锁，下一个会话可重新触发

---

## 三、InProcessTeammateTask - 同进程队友协作

这是 Claude Code 的独特创新，允许**多个 Agent 在同一进程中并发运行**，共享资源但隔离上下文。

### 3.1 架构设计

```
Leader Agent (主)
    |
    +-- Teammate 1 (AsyncLocalStorage 隔离)
    +-- Teammate 2 (AsyncLocalStorage 隔离)
    +-- Teammate 3 (AsyncLocalStorage 隔离)
```

**关键隔离机制**：
- **AsyncLocalStorage**：每个 Teammate 的上下文（agentId、teamName、权限等）独立
- **独立 AbortController**：Teammate 不与 Leader 的中断信号关联
- **文件邮箱**：Teammate 之间通过 `~/.claude/teams/<team>/mail/<name>.jsonl` 通信

### 3.2 InProcessTeammateTaskState

```typescript
type InProcessTeammateTaskState = TaskStateBase & {
  type: 'in_process_teammate'
  
  // 身份
  identity: TeammateIdentity {
    agentId: string              // "researcher@my-team"
    agentName: string            // "researcher"
    teamName: string             // "my-team"
    color?: string               // UI 着色
    planModeRequired: boolean
    parentSessionId: string
  }
  
  // 执行
  prompt: string
  model?: string
  selectedAgent?: AgentDefinition
  abortController?: AbortController     // 独立的中止控制器
  currentWorkAbortController?: AbortController  // 单轮中止
  
  // 协作
  permissionMode: PermissionMode        // 独立权限模式（可通过 Shift+Tab 切换）
  awaitingPlanApproval: boolean         // Plan mode 等待批准
  pendingUserMessages: string[]         // 消息邮箱接收的消息
  
  // UI
  messages?: Message[]                   // 对话历史（上限 50 条防止 OOM）
  spinnerVerb?: string                  // 动画文本（"思考中…" 等）
  pastTenseVerb?: string                // 完成时使用
  
  // 生命周期
  isIdle: boolean
  shutdownRequested: boolean
  onIdleCallbacks?: Array<() => void>   // 当 Teammate 空闲时调用
}
```

### 3.3 TeamCreate & SendMessage 工具

**TeamCreate** - 创建一个新的 Team：
```typescript
TeamCreate({
  team_name: "research-team",
  description: "Finding bugs and design issues",
  agent_type: "lead"  // 可选，默认 "team-lead"
})
// 返回：
{
  team_name: "research-team",
  team_file_path: "~/.claude/teams/research-team/team.json",
  lead_agent_id: "team-lead@research-team"
}
```

**Team 文件结构** (`~/.claude/teams/<team>/team.json`)：
```json
{
  "name": "research-team",
  "leadAgentId": "team-lead@research-team",
  "leadSessionId": "<session-id>",
  "members": [
    {
      "agentId": "team-lead@research-team",
      "name": "team-lead",
      "agentType": "lead",
      "model": "claude-3-5-sonnet",
      "joinedAt": 1234567890,
      "cwd": "/project",
      "subscriptions": []
    }
  ]
}
```

**SendMessage** - Leader 或 Teammate 之间通信：
```typescript
// Teammate 向 Leader 发送消息
SendMessage({
  to: "*",  // "*" 表示广播
  message: "Found 3 bugs in auth module",
  summary: "Bug report: auth issues"
})

// Leader 向 Teammate 发送指令
SendMessage({
  to: "researcher",
  message: "Fix the null pointer in validate.ts:42. ...",
  summary: "Implement null pointer fix"
})
```

**消息邮箱** (`~/.claude/teams/<team>/mail/<name>.jsonl`)：
- 每条消息是一个 JSON 行
- Teammate 启动时读取邮箱，处理消息
- 支持特殊消息类型：`shutdown_request`、`plan_approval_response`、`permission_response`

---

## 四、Swarm 机制与后端抽象

Claude Code 的 Swarm 是**多执行后端的统一抽象**，核心思想：

> Teammates 可以在不同的执行环境中运行，但 API 和通信方式保持一致

### 4.1 后端类型

```typescript
type BackendType = 'tmux' | 'iterm2' | 'in-process'

// 后端检测和选择
const backend = await detectAndGetBackend()  // 自动检测当前环境
const backend = getBackendByType('in-process')  // 手动指定
```

### 4.2 PaneBackend 接口（针对终端 Pane）

```typescript
interface PaneBackend {
  readonly type: BackendType
  readonly displayName: string
  readonly supportsHideShow: boolean
  
  // 检查可用性
  isAvailable(): Promise<boolean>
  isRunningInside(): Promise<boolean>
  
  // Pane 操作
  createTeammatePaneInSwarmView(name: string, color: string): Promise<CreatePaneResult>
  sendCommandToPane(paneId: PaneId, command: string): Promise<void>
  setPaneBorderColor(paneId: PaneId, color: string): Promise<void>
  setPaneTitle(paneId: PaneId, name: string, color: string): Promise<void>
  killPane(paneId: PaneId): Promise<boolean>
  hidePane(paneId: PaneId): Promise<boolean>
  showPane(paneId: PaneId, targetWindow: string): Promise<boolean>
  
  // 布局管理
  rebalancePanes(windowTarget: string, hasLeader: boolean): Promise<void>
}
```

### 4.3 TeammateExecutor 接口（高级）

```typescript
interface TeammateExecutor {
  readonly type: BackendType
  
  // 生命周期
  isAvailable(): Promise<boolean>
  spawn(config: TeammateSpawnConfig): Promise<TeammateSpawnResult>
  sendMessage(agentId: string, message: TeammateMessage): Promise<void>
  terminate(agentId: string, reason?: string): Promise<boolean>
  kill(agentId: string): Promise<boolean>
  isActive(agentId: string): Promise<boolean>
}
```

### 4.4 InProcessBackend 实现细节

与 Tmux/iTerm2 不同，InProcessBackend 使用**文件邮箱进行通信**：

```typescript
// InProcessBackend.spawn()
// 1. 调用 spawnInProcessTeammate() 创建 TeammateContext
// 2. 注册 InProcessTeammateTaskState 到 AppState
// 3. 启动 startInProcessTeammate() 的 Agent 执行循环
// 4. 返回 abortController（用于 kill）

// InProcessBackend.sendMessage()
// 写入到文件邮箱：~/.claude/teams/<team>/mail/<name>.jsonl

// InProcessBackend.terminate()
// 1. 生成 shutdown_request 消息
// 2. 写入到邮箱
// 3. 设置 task.shutdownRequested = true
// 4. Teammate 的 Agent 循环检测到标志，正常退出

// InProcessBackend.kill()
// 1. 调用 abortController.abort()
// 2. 中断所有进行中的 Promise
// 3. 更新 Task 状态为 'killed'
```

---

## 五、Git 操作协调（gitOperationTracking）

Claude Code 在**单一会话内**通过正则表达式追踪 Git 操作，目的是：
1. **分析与上报**：统计 commit、push、PR 创建等操作用于分析
2. **会话关联**：从 PR URL 提取信息，自动关联会话到 GitHub PR
3. **多 Agent 场景**：多个 Agent 的 git 操作都被独立追踪

```typescript
// 检测 Git 操作的流程
export function detectGitOperation(
  command: string,
  output: string,
): {
  commit?: { sha: string; kind: CommitKind }  // 'committed' | 'amended' | 'cherry-picked'
  push?: { branch: string }
  branch?: { ref: string; action: BranchAction }  // 'merged' | 'rebased'
  pr?: { number: number; url?: string; action: PrAction }  // 'created' | 'edited' | 'merged' ...
}

// 支持的操作
// - git commit (含 --amend)
// - git cherry-pick
// - git push
// - git merge / git rebase
// - gh pr create / edit / merge / comment / close / ready
// - glab mr create
// - curl POST 到 PR 端点
```

**在多 Agent 场景中**：
- 目前 Git 协调**没有中央锁**，Agent 必须协商或依赖 git 的自身冲突处理
- Nutshell 的 GitCoordinator（中央协调锁）是一个改进方向

---

## 六、权限和隔离机制

### 6.1 权限模式

```typescript
type PermissionMode = 
  | 'default'          // 提示用户每个敏感操作
  | 'acceptEdits'      // 自动接受文件编辑
  | 'plan'             // Plan mode：先审批计划再执行
  | 'auto'             // 自动分类批准（需 GrowthBook 特性门控）
  | 'bubble'           // 权限请求冒泡到父 Agent
  | 'bypassPermissions' // 完全跳过（danger）
```

### 6.2 In-Process Teammate 权限流

```
Teammate 调用敏感工具（如 Bash）
    |
    ├─ 检查权限规则 hasPermissionsToUseTool()
    |    返回 { behavior: 'allow' | 'ask' | 'deny', ... }
    |
    ├─ 若为 'ask'，发起权限请求
    |    |
    |    ├─ 优先路径：getLeaderToolUseConfirmQueue()
    |    |    └─ Leader 的 ToolUseConfirm 对话框显示 teammate badge
    |    |    └─ 用户决定 -> onAllow/onReject 回调
    |    |
    |    └─ 降级路径：文件邮箱
    |         └─ Teammate 的邮箱中发起 permission_request
    |         └─ Leader 读取邮箱，通过 Shift+P 响应
    |         └─ Teammate 轮询邮箱等待响应
    |
    └─ 返回决定
```

### 6.3 Tool Restriction 设计

AgentTool 支持细粒度权限限制：

```typescript
// Agent 定义中声明 tools
{
  tools: [
    'Bash',                              // 完全允许
    'Bash:grep',                         // 仅允许特定参数
    'FileEdit:*.md',                    // 仅允许编辑 .md 文件
    'Agent<worker,researcher>',         // 仅允许派生特定类型的 Agent
  ],
  disallowedTools: [
    'FileDelete',                       // 禁止删除
  ]
}
```

---

## 七、CoordinatorMode - 多 Worker 编排

Claude Code 实验中的 **Coordinator Mode** 让主 Agent 充当协调者，派生多个 Worker 执行具体任务：

```typescript
function getCoordinatorSystemPrompt(): string {
  return `You are Claude Code, an AI assistant that orchestrates software engineering tasks across multiple workers.

## 1. Your Role
- Help the user achieve their goal
- Direct workers to research, implement and verify code changes
- Synthesize results and communicate with the user

## 2. Your Tools
- Agent - Spawn a new worker
- SendMessage - Continue an existing worker
- TaskStop - Stop a running worker
...
`
}
```

**Coordinator 工作流**：
1. **研究阶段**（并发）：派生多个 Worker 并行探索代码
2. **综合阶段**（序列）：Coordinator 读取所有 Worker 的结果，理解问题
3. **实现阶段**（并发+序列）：根据理解派生新的 Worker 实现修改
4. **验证阶段**（并发）：派生 Verifier Worker 测试修改

**任务通知格式**（与 LocalAgentTask 相同）：
```xml
<task-notification>
  <task-id>agent-xyz</task-id>
  <status>completed|failed|killed</status>
  <summary>Worker "Research auth module" completed</summary>
  <result>Found 3 files in src/auth: validate.ts, token.ts, session.ts</result>
  <usage>
    <total_tokens>45000</total_tokens>
    <tool_uses>12</tool_uses>
    <duration_ms>120000</duration_ms>
  </usage>
</task-notification>
```

---

## 八、Agent 内存管理与进度追踪

### 8.1 LocalAgentTask 的进度追踪

```typescript
// 在 Agent 每一轮转换后调用
function updateProgressFromMessage(
  tracker: ProgressTracker,
  message: Message,
  resolveActivityDescription?: ActivityDescriptionResolver,
  tools?: Tools
): void {
  // 更新 token 计数（输入累积，输出求和）
  tracker.latestInputTokens = usage.input_tokens
  tracker.cumulativeOutputTokens += usage.output_tokens
  
  // 记录每个工具调用
  for (const content of message.message.content) {
    if (content.type === 'tool_use') {
      tracker.toolUseCount++
      tracker.recentActivities.push({
        toolName: content.name,
        input: content.input,
        activityDescription: resolveActivityDescription?.(content.name, content.input),
        isSearch: ...,
        isRead: ...
      })
    }
  }
  
  // 只保留最近 5 个活动（防止 OOM）
  while (tracker.recentActivities.length > 5) {
    tracker.recentActivities.shift()
  }
}

// 生成 AgentProgress（用于 UI 显示和通知）
type AgentProgress = {
  toolUseCount: number
  tokenCount: number  // input + output
  lastActivity?: ToolActivity
  recentActivities?: ToolActivity[]
  summary?: string  // 后台汇总器设置的 1-2 句总结
}
```

### 8.2 后台汇总（Agent Summarization）

```typescript
// 定期汇总 Agent 的进度为自然语言
function updateAgentSummary(
  taskId: string,
  summary: string,  // 模型生成的 1-2 句总结
  setAppState: SetAppState
): void {
  // 保存 token/工具计数
  updateTaskState<LocalAgentTaskState>(taskId, setAppState, task => ({
    ...task,
    progress: {
      ...task.progress,
      summary
    }
  }))
  
  // 发送到 SDK 消费者（VS Code 侧边栏）
  if (getSdkAgentProgressSummariesEnabled()) {
    emitTaskProgress({
      taskId,
      description: summary,
      tokenCount: ...,
      toolUseCount: ...
    })
  }
}
```

---

## 九、消息和通知机制

### 9.1 Task 通知队列

所有 Agent（LocalAgent、RemoteAgent、Teammate）完成时都通过**消息队列**推送通知：

```typescript
// 在 messageQueueManager.ts 中
enqueuePendingNotification({
  value: `<task-notification>...</task-notification>`,
  mode: 'task-notification'  // 特殊消息类型
})

// 主 Agent 的下一轮对话将接收到
User:
  <task-notification>
  <task-id>agent-xyz</task-id>
  <status>completed</status>
  ...
  </task-notification>
```

### 9.2 Teammate 邮箱系统

Teammate 与外界通信通过**文件邮箱**而非直接调用：

```
~/.claude/teams/<team>/mail/<agent-name>.jsonl

[JSON] {"from": "leader", "text": "Fix the null pointer", "timestamp": "2026-04-01T..."}
[JSON] {"from": "leader", "text": "{\"type\":\"shutdown_request\",\"requestId\":\"...\"}", ...}
```

**邮箱消息类型**：
- `plain_text` - 普通消息
- `shutdown_request` - Leader 请求 Teammate 退出
- `permission_request` - 权限请求（由权限系统发起）
- `permission_response` - Leader 的权限决定
- `plan_approval_response` - Plan mode 的批准/拒绝

---

## 十、对 Nutshell 的改进建议

### 10.1 架构对标

| 功能 | Nutshell | Claude Code | 改进建议 |
|------|---------|-----------|--------|
| **子 Agent 启动** | `spawn_session()` 创建进程 | `AgentTool()` 异步注册 Task，前端立即显示 | 前端优先反馈，后端异步执行 |
| **隔离机制** | 进程隔离（heavy） | AsyncLocalStorage（light） + 文件邮箱 | 考虑轻量级隔离减少开销 |
| **通信方式** | 文件 IPC (context.jsonl) | 文件邮箱 + AppState 通知队列 | 邮箱系统设计更清晰 |
| **任务管理** | TaskList 外部管理 | AppState 集成，统一生命周期 | AppState 模式更易追踪 |
| **权限协调** | GitCoordinator | Git 操作通过正则追踪 | 考虑添加中央 Git 锁 |
| **进度通知** | 定期轮询 | 实时 progress events + 后台汇总 | 更及时的用户反馈 |
| **后端抽象** | 单一进程后端 | PaneBackend + TeammateExecutor | 支持多执行环境 |

### 10.2 具体改进方向

**1. 异步任务框架**
```python
# Nutshell 可参考 Claude Code 的设计
# 任务在注册时立即返回 task_id，UI 显示 loading
# 后台异步运行，通过消息队列推送进度和完成通知
# 优点：更好的 UX，前端不被阻塞

class Task(TypedDict):
    id: str
    status: 'running' | 'completed' | 'failed' | 'killed'
    progress: TaskProgress
    result: Any
    evictAfter: Optional[int]  # GC 优雅期

@dataclass
class TaskProgress:
    toolUseCount: int
    tokenCount: int
    lastActivity: Optional[str]
    summary: Optional[str]  # 后台汇总
```

**2. AsyncLocalStorage 替代方案**
```python
# Python 中的等价物：contextvars
from contextvars import ContextVar

teammate_context: ContextVar[Optional[TeammateContext]] = ContextVar(
    'teammate_context', 
    default=None
)

# 派生子 Agent 时
token = teammate_context.set(context)
try:
    # 子 Agent 执行
    result = run_agent(prompt)
finally:
    teammate_context.reset(token)
```

**3. 邮箱系统标准化**
```python
# 目前 nutshell 的 context.jsonl/events.jsonl 可演进为
# 专用的邮箱系统（类似 Claude Code）：

# ~/.nutshell/teams/<team>/mail/<agent-name>.jsonl
# 每条消息的标准格式：
{
  "id": "msg-uuid",
  "from": "agent-name",
  "type": "text" | "shutdown_request" | "permission_request" | ...,
  "content": "...",
  "timestamp": "2026-04-01T...",
  "read": false
}

# 优点：
# - 清晰的消息契约
# - 支持 read 标志防止重复处理
# - 支持消息类型扩展
```

**4. 中央 Git 协调**
```python
# 当前：个别 Agent 执行 git 操作，gitOperationTracking 后追踪
# 改进：Git 操作前申请许可证

class GitLock:
    """中央 Git 操作协调"""
    
    async def acquire(self, agent_id: str, operation: str, paths: List[str]) -> str:
        """申请 Git 锁，返回许可证 ID"""
        # 检查冲突（是否有其他 Agent 在操作相同的文件）
        # 如有冲突，等待或拒绝
        pass
    
    async def release(self, permit_id: str) -> None:
        """释放锁"""
        pass

# Agent 使用
async with git_lock.acquire(agent_id, 'commit', ['src/auth.ts']):
    # 执行 git 操作
    pass
```

**5. 进度汇总模型**
```python
# Claude Code 的进度追踪和后台汇总值得参考

@dataclass
class ActivityDescription:
    toolName: str
    input: Dict
    description: str  # "Reading src/foo.ts"
    isSearch: bool
    isRead: bool

class ProgressTracker:
    toolUseCount: int = 0
    latestInputTokens: int = 0
    cumulativeOutputTokens: int = 0
    recentActivities: List[ActivityDescription] = field(default_factory=list)
    
    def record_activity(self, activity: ActivityDescription):
        self.recentActivities.append(activity)
        if len(self.recentActivities) > 5:
            self.recentActivities.pop(0)

# 后台汇总线程
async def background_summarizer(task_id: str):
    while not task_finished(task_id):
        await asyncio.sleep(10)  # 10 秒汇总一次
        summary = await generate_summary(get_task_progress(task_id))
        update_task_summary(task_id, summary)
```

**6. 多执行后端支持**
```python
# Claude Code 支持 Tmux、iTerm2、In-Process
# Nutshell 可考虑添加：

class TeammateBackend(ABC):
    @abstractmethod
    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        pass
    
    @abstractmethod
    async def send_message(self, agent_id: str, message: str) -> None:
        pass
    
    @abstractmethod
    async def kill(self, agent_id: str) -> None:
        pass

class InProcessBackend(TeammateBackend):
    """在同进程运行，通过 contextvars 隔离"""
    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        # 创建 contextvars.Token，启动子 Agent
        pass

class ProcessBackend(TeammateBackend):
    """创建独立进程"""
    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        # subprocess.Popen
        pass

# 检测和选择
backend = detect_available_backend()  # 自动选择
backend = get_backend('in-process')   # 手动指定
```

---

## 十一、设计原则总结

Claude Code 的多 Agent 架构遵循以下原则：

1. **前端优先**：任务立即注册到 UI，用户看到进度而不是等待
2. **异步默认**：Agent 在后台运行，不阻塞主线程
3. **通知驱动**：完成时推送消息，而不是轮询
4. **轻量级隔离**：AsyncLocalStorage + 文件邮箱，避免重进程开销
5. **后端无关**：抽象 PaneBackend 和 TeammateExecutor，支持多种执行环境
6. **细粒度权限**：每个 Agent 独立权限模式，支持权限冒泡和自动批准
7. **内存管理**：进度和消息受上限，后台汇总压缩旧对话
8. **Git 追踪**：操作后分析而不是操作前阻塞（可改进为前期许可）

---

## 附录：关键文件对应表

| 功能 | 文件 | 关键类型/函数 |
|------|------|-------------|
| **Agent 工具** | `src/tools/AgentTool/runAgent.ts` | `runAgent()` generator |
| **任务管理** | `src/tasks/types.ts` | `TaskState` union |
| **本地 Agent 任务** | `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | `LocalAgentTaskState`, `ProgressTracker` |
| **远程 Agent 任务** | `src/tasks/RemoteAgentTask/RemoteAgentTask.tsx` | `RemoteAgentTaskState`, 轮询机制 |
| **Teammate 任务** | `src/tasks/InProcessTeammateTask/types.ts` | `InProcessTeammateTaskState` |
| **梦想任务** | `src/tasks/DreamTask/DreamTask.ts` | `DreamTaskState`, 内存巩固 |
| **Swarm 后端** | `src/utils/swarm/backends/types.ts` | `PaneBackend`, `TeammateExecutor` |
| **In-Process 后端** | `src/utils/swarm/backends/InProcessBackend.ts` | 邮箱通信实现 |
| **Team 创建** | `src/tools/TeamCreateTool/TeamCreateTool.ts` | Team 文件初始化 |
| **消息发送** | `src/tools/SendMessageTool/SendMessageTool.ts` | 邮箱写入 |
| **上下文隔离** | `src/utils/teammateContext.ts` | `AsyncLocalStorage` 包装 |
| **In-Process 生成** | `src/utils/swarm/spawnInProcess.ts` | `spawnInProcessTeammate()` |
| **In-Process 执行** | `src/utils/swarm/inProcessRunner.ts` | `startInProcessTeammate()`, 权限流 |
| **Git 追踪** | `src/tools/shared/gitOperationTracking.ts` | 正则检测、事件上报 |
| **Agent 内存** | `src/tools/AgentTool/agentMemory.ts` | 内存范围和目录 |
| **内存快照** | `src/tools/AgentTool/agentMemorySnapshot.ts` | Snapshot 同步逻辑 |
| **Fork 子 Agent** | `src/tools/AgentTool/forkSubagent.ts` | 隐式派生、对话继承 |
| **协调器模式** | `src/coordinator/coordinatorMode.ts` | Worker 系统提示 |
| **多 Agent 生成** | `src/tools/shared/spawnMultiAgent.ts` | 生成共享函数 |

