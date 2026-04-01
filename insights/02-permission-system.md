# Claude Code 权限系统、工具设计和沙箱机制 — 深度分析

## 执行摘要

Claude Code 实现了一个分层、多策略的权限系统，相比简单的黑名单/白名单方式更为复杂和完善。核心机制包括：

1. **权限模式系统**（5种+ 隐藏的auto模式）
2. **多源规则引擎**（7个权限规则来源）
3. **动态分类器**（AI-powered auto-mode，需TRANSCRIPT_CLASSIFIER特性开启）
4. **工具级安全隔离**（Worktree、Plan Mode）
5. **深度Bash安全检测**（20+ 种安全检查）
6. **沙箱适配器**（@anthropic-ai/sandbox-runtime）

---

## 一、权限模型详解

### 1.1 权限模式体系 (PermissionMode)

**定义位置**：`src/types/permissions.ts` + `src/utils/permissions/PermissionMode.ts`

```typescript
// 外部可见模式（用户配置）
EXTERNAL_PERMISSION_MODES = [
  'acceptEdits',      // 自动接受编辑类工具
  'bypassPermissions', // 绕过所有权限检查
  'default',          // 逐项询问（默认）
  'dontAsk',          // 拒绝所有请求
  'plan'              // 计划模式（只读）
]

// 内部模式（还包括）
PERMISSION_MODES = [
  ...EXTERNAL_PERMISSION_MODES,
  'auto'   // 仅Ant内部，需TRANSCRIPT_CLASSIFIER特性，AI分类器决定
  'bubble' // 内部机制，权限请求冒泡到父Agent
]
```

**模式转换流程**：
- 用户可通过 `/permissions` 命令或设置文件配置默认模式
- `EnterPlanModeTool` 可运行时切换到 `plan` 模式
- `plan` 模式自动在 `prePlanMode` 字段存储上一个模式，`ExitPlanModeTool` 恢复
- `auto` 模式切换时会触发 `handleAutoModeTransition()`，激活分类器

### 1.2 权限规则的7个来源 (PermissionRuleSource)

**优先级顺序**（高到低）：

```typescript
PERMISSION_RULE_SOURCES = [
  ...SETTING_SOURCES,  // userSettings, projectSettings, localSettings, flagSettings, policySettings
  'cliArg',           // 命令行 --allow-bash "git *" 参数
  'command',          // 交互式命令（如/permissions UI中添加的规则）
  'session'           // 本会话临时规则
]
```

**关键机制**：
- 不同来源的规则独立存储在 `ToolPermissionContext` 的 `alwaysAllowRules`, `alwaysDenyRules`, `alwaysAskRules`
- 权限持久化时指定 `destination`，决定写入哪个配置源

### 1.3 权限决策流程

```
Tool Call
  ↓
validateInput()    [工具级预检]
  ↓
checkPermissions() [工具级检查]
  ↓
hasPermissionsToUseTool()
  ├─→ 配置级许可？(config allow/deny) → 返回 allow/deny
  ├─→ 是否需要提示？(ask)
  │   ├─→ 运行钩子 (PermissionRequest hooks)
  │   ├─→ 运行分类器 (BASH_CLASSIFIER/TRANSCRIPT_CLASSIFIER)
  │   ├─→ 交互式处理 (interactive permission handler)
  │   │   ├─→ 推送到权限队列
  │   │   ├─→ 后台运行分类器和钩子
  │   │   ├─→ 用户交互触发清除分类器标志
  │   │   └─→ 显示权限对话
  │   └─→ 返回决策
  └─→ 日志记录（analytics + OTel telemetry）
```

**决策来源**：
- `'config'` - 配置文件白名单/黑名单
- `'user'` - 用户在提示框中批准，分 `permanent`（持久）和临时
- `'classifier'` - AI分类器（auto-mode 或 BASH_CLASSIFIER）
- `'hook'` - 权限钩子系统

---

## 二、BashTool的危险命令检测与沙箱机制

### 2.1 安全检查体系（bashSecurity.ts）

**20+ 种安全检查**（通过 `BASH_SECURITY_CHECK_IDS` 编号）：

| ID | 检查名 | 说明 |
|---|---|------|
| 1 | INCOMPLETE_COMMANDS | 不完整的命令 |
| 2 | JQ_SYSTEM_FUNCTION | jq 中的 system() 函数 |
| 3 | JQ_FILE_ARGUMENTS | jq 的文件参数危险性 |
| 4 | OBFUSCATED_FLAGS | 混淆的标志 |
| 5 | SHELL_METACHARACTERS | 未引用的shell元字符 |
| 6 | DANGEROUS_VARIABLES | 危险变量（如IFS） |
| 7 | NEWLINES | 嵌入式换行符（注入向量） |
| 8-10 | COMMAND_SUBSTITUTION* | `$()`, `${...}` 等 |
| 11 | IFS_INJECTION | IFS变量注入 |
| 12 | GIT_COMMIT_SUBSTITUTION | git commit message中的替换 |
| 13 | PROC_ENVIRON_ACCESS | /proc/self/environ 访问 |
| 14 | MALFORMED_TOKEN_INJECTION | 格式错误的令牌 |
| 15 | BACKSLASH_ESCAPED_WHITESPACE | 反斜杠转义空白 |
| 16 | BRACE_EXPANSION | 大括号扩展 |
| 17 | CONTROL_CHARACTERS | 控制字符 |
| 18 | UNICODE_WHITESPACE | Unicode空白字符 |
| 19 | MID_WORD_HASH | 单词中间的#注释 |
| 20 | ZSH_DANGEROUS_COMMANDS | Zsh特定危险命令 |

**关键防御**：

```typescript
// Zsh安全性（ZSH_DANGEROUS_COMMANDS集合）
const ZSH_DANGEROUS_COMMANDS = new Set([
  'zmodload',   // 门槛到危险模块
  'emulate',    // eval等价物
  'sysopen', 'sysread', 'syswrite',  // 文件I/O绕过
  'zpty',       // 伪终端命令执行
  'ztcp',       // TCP连接（数据泄露）
  'zf_rm', 'zf_mv', 'zf_chmod'  // 内置命令绕过
])

// 进程替换检测
COMMAND_SUBSTITUTION_PATTERNS = [
  { pattern: /<\(/, message: '进程替换 <()' },
  { pattern: /=\(/, message: 'Zsh等号扩展 =()' },  // =curl 绕过Bash(curl:*)规则
]
```

**安全重定向剥离**（`stripSafeRedirections`）：
```typescript
// 移除安全的重定向模式，避免被规则意外白名单化
.replace(/\s+2\s*>&\s*1(?=\s|$)/g, '')      // 2>&1
.replace(/[012]?\s*>\s*\/dev\/null(?=\s|$)/g, '') // > /dev/null
.replace(/\s*<\s*\/dev\/null(?=\s|$)/g, '')  // < /dev/null
// 关键：尾部边界检查 (?=\s|$) 防止 /dev/nullo 被误识别
```

### 2.2 复合命令限制

```typescript
export const MAX_SUBCOMMANDS_FOR_SECURITY_CHECK = 50
// 超过50个子命令时降级到'ask'（防止DoS）

export const MAX_SUGGESTED_RULES_FOR_COMPOUND = 5
// 用户链式写命令时避免建议10+个规则
```

### 2.3 自动模式分类器（yoloClassifier.ts）

**触发条件**：
- `feature('TRANSCRIPT_CLASSIFIER')` 已启用
- 用户进入 `auto` 模式

**输入/输出**：
- 输入：命令、当前权限规则、CLAUDE.md内容（缓存）
- 输出：allow/soft_deny/environment 决策 + 置信度 + 匹配规则

**危险规则剥离**：
```typescript
// 进入auto模式时自动移除危险规则
export function isDangerousBashPermission(toolName, ruleContent): boolean {
  // Bash(*) 或 Bash 无参数 = 允许所有命令 → 危险
  // python:*, node:*, ssh:* 等 → 允许任意代码执行 → 危险
}
```

**拒绝追踪**（denialTracking.ts）：
```typescript
DENIAL_LIMITS = {
  'hour': 5,        // 每小时5次拒绝→fallback to prompting
  'session': 20     // 每会话20次拒绝
}
// 拒绝过于频繁时，回到交互式提示（避免分类器失败时完全卡死）
```

---

## 三、Plan Mode 设计

### 3.1 目的与动机

Plan Mode 是一种**只读探索模式**，让 Claude 在修改代码前先制定计划并获得用户批准。

**进入时的指示**：
```
In plan mode, you should:
1. Thoroughly explore the codebase
2. Identify similar features
3. Consider multiple approaches
4. Use AskUserQuestion if you need to clarify
5. Design a concrete implementation strategy
6. When ready, use ExitPlanMode to present your plan
```

### 3.2 实现机制

```typescript
// EnterPlanModeTool
async call(_input, context) {
  // 1. 保存当前模式
  context.setAppState(prev => ({
    ...prev,
    toolPermissionContext: applyPermissionUpdate(
      prepareContextForPlanMode(prev.toolPermissionContext),
      { type: 'setMode', mode: 'plan', destination: 'session' }
    )
  }))
}

// ExitPlanModeTool 恢复
context.setAppState(prev => ({
  ...prev,
  toolPermissionContext: {
    ...prev.toolPermissionContext,
    mode: prev.toolPermissionContext.prePlanMode ?? 'default'
  }
}))
```

**Plan Mode下编辑工具自动拒绝**：
```typescript
// Edit, Write, NotebookEdit 等被自动拒绝
if (permissionMode === 'plan') {
  return { behavior: 'deny', message: 'Cannot edit in plan mode' }
}
```

---

## 四、Worktree 隔离设计

### 4.1 目的

Worktree 提供**文件系统级别的会话隔离**：不仅创建 git worktree，还切换 session 的 CWD，让 Agent 完全在隔离环境中工作。

### 4.2 实现细节

```typescript
// EnterWorktreeTool.ts
async call(input) {
  // 验证不在已有的worktree中
  const mainRepoRoot = findCanonicalGitRoot(getCwd())
  
  // 创建worktree（对应新git分支）
  const worktreeSession = await createWorktreeForSession(getSessionId(), slug)
  
  // 切换session到worktree
  process.chdir(worktreeSession.worktreePath)
  setCwd(worktreeSession.worktreePath)
  setOriginalCwd(getCwd())  // 重置原始CWD
  
  // 清除缓存，重新计算环境信息
  clearSystemPromptSections()  // 刷新env_info_simple
  clearMemoryFileCaches()      // CLAUDE.md缓存失效
}
```

**清理与退出**：
```typescript
// ExitWorktreeTool
async call(action: 'keep' | 'remove', discard_changes?: boolean) {
  if (action === 'remove') {
    if (!discard_changes && hasUncommittedChanges) {
      throw new Error('Cannot remove with uncommitted changes')
    }
    removeWorktreeForSession(session)
  }
  
  // 返回到原始CWD
  process.chdir(getOriginalCwd())
  setCwd(getOriginalCwd())
}
```

**隔离维度**：
1. **文件系统隔离** - 不同的工作目录分支
2. **Git隔离** - 独立的分支/reflog
3. **Session状态隔离** - CWD改变，系统提示重新计算
4. **记忆缓存清除** - CLAUDE.md路径缓存失效

---

## 五、Tool.ts 接口规范

### 5.1 核心接口

```typescript
export type Tool<Input, Output, P> = {
  name: string
  aliases?: string[]                    // 向后兼容别名
  searchHint?: string                   // ToolSearch关键字（延迟加载）
  shouldDefer?: boolean                 // 延迟加载（via ToolSearch）
  alwaysLoad?: boolean                  // 强制第一轮加载

  // 行为定义
  isEnabled(): boolean
  isConcurrencySafe(input): boolean
  isReadOnly(input): boolean
  isDestructive(input): boolean         // 标记删除/覆写/发送操作

  // 权限与验证
  validateInput?(input, context): Promise<ValidationResult>
  checkPermissions(input, context): Promise<PermissionResult>
  getPath?(input): string

  // 执行
  call(input, context, canUseTool, parentMessage, onProgress?): Promise<ToolResult<Output>>
  
  // 分类器
  toAutoClassifierInput(input): unknown
  isSearchOrReadCommand?(input): { isSearch, isRead, isList? }
  isReadOnly(input): boolean
  
  // UI渲染
  renderToolUseMessage(input, options): React.ReactNode
  renderToolResultMessage?(output, progress, options): React.ReactNode
}
```

### 5.2 Fail-closed 默认值设计（buildTool）

```typescript
const TOOL_DEFAULTS = {
  isEnabled: () => true,
  isConcurrencySafe: (_input?) => false,  // fail-closed: 假设不安全
  isReadOnly: (_input?) => false,         // fail-closed: 假设有写操作
  isDestructive: (_input?) => false,
  checkPermissions: (input, _ctx?) =>     // 默认允许
    Promise.resolve({ behavior: 'allow', updatedInput: input }),
  toAutoClassifierInput: (_input?) => '', // skip classifier
}
```

**Fail-closed原则**：
- `isConcurrencySafe` 默认false → 要求工具证明自己是并发安全的
- `isReadOnly` 默认false → 要求工具证明自己是只读的

### 5.3 ToolSearch 延迟加载

```typescript
// 工具设置 shouldDefer: true 后，不在第一轮注入到系统提示
// 用户需要通过 ToolSearchTool 按名称或关键字激活
// searchHint 用于 ToolSearch 的语义匹配

// 优点：减少 prompt 长度，提高 token 效率
// 相关工具：ToolSearchTool
```

---

## 六、Hooks 系统设计

### 6.1 PermissionRequest 钩子

```typescript
// 每个钩子可定义：
{
  tool: 'Bash' | 'Edit' | '*'        // 工具名或通配符
  if: string                         // 权限规则模式，如 "git *"
  behavior: 'allow' | 'deny' | 'ask'
  message?: string                   // 拒绝时的解释
  interrupt?: boolean                // 中断session
  permissions?: [{
    behavior: 'allow' | 'deny'
    rules: ['git *', 'npm *']
  }]
}
```

### 6.2 交互式钩子处理（竞速模型）

```typescript
// interactiveHandler.ts
function handleInteractivePermission(params, resolve) {
  // 1. 推送权限队列（UI显示）
  ctx.pushToQueue({ ... onAllow, onReject })
  
  // 2. 后台运行钩子
  for await (const hookResult of executePermissionRequestHooks(...)) {
    if (hookResult.behavior === 'allow') {
      resolve(buildAllow(...))
      return
    }
  }
  
  // 3. 分类器与用户交互竞速
  const classifierPromise = peekSpeculativeClassifierCheck(command)
  const raceResult = await Promise.race([
    classifierPromise,
    new Promise(res => setTimeout(res, 2000, { type: 'timeout' }))
  ])
  
  if (raceResult.type === 'result' && raceResult.result.matches) {
    resolve(buildAllow(...))
    return
  }
  
  // 4. 等待用户交互
}
```

---

## 七、对比与改进建议

### 对比表

| 特性 | Claude Code | Nutshell | 改进建议 |
|-----|-----------|---------|--------|
| 权限模式 | 5+种（default, plan, acceptEdits等） | 无 | 引入权限模式枚举 |
| 规则来源 | 7个（settings, cli, hooks等） | 2-3个（allow/deny lists） | 多源规则合并系统 |
| Bash安全检查 | 20+ 种 | 基础pattern检查 | 引入Quote感知、Zsh防御、边界保护 |
| 只读约束 | Plan Mode + isReadOnly() | venv隔离 | 实现Plan Mode + ReadOnly验证 |
| AI分类器 | TRANSCRIPT_CLASSIFIER | 无 | 可选集成 |
| 钩子系统 | PermissionRequest hooks | 无 | 实现hooks系统 |
| Worktree隔离 | 完整支持（git + hooks） | 无 | WorktreeSession上下文管理 |
| 分类器隔离 | 危险规则自动剥离 | 无 | 进入classifier模式时验证规则安全性 |
| 拒绝追踪 | DENIAL_LIMITS限流 | 无 | 添加拒绝计数，超限回到交互式 |
| 工具延迟加载 | shouldDefer + ToolSearch | 无 | 减少prompt长度 |

### 改进建议（优先级排序）

**P0 - 可直接实现**：
```python
# 1. 权限模式
class PermissionMode(Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "accept_edits"
    BYPASS = "bypass"
    DONT_ASK = "dont_ask"
    PLAN = "plan"  # 只读

# 2. Plan Mode 实现
class PlanMode:
    def __enter__(self):
        self.prev_mode = executor.permission_mode
        executor.permission_mode = PermissionMode.PLAN
    
    def __exit__(self, *args):
        executor.permission_mode = self.prev_mode

# 3. Fail-closed 工具接口
class Tool(ABC):
    def is_read_only(self, input: dict) -> bool:
        return False  # 默认假设有写操作
    
    def is_concurrency_safe(self, input: dict) -> bool:
        return False  # 默认假设不安全
```

**P1 - 增强安全检查**：
```python
# bash_security.py 增强
class BashSecurityChecker:
    ZSH_DANGEROUS = {'zmodload', 'emulate', 'sysopen', 'ztcp', 'zpty'}
    
    def check(self, command: str) -> list[SecurityIssue]:
        quoted_content = self.extract_quoted(command)
        unquoted = self.strip_quotes(command)
        
        issues = []
        # 检查命令替换
        if re.search(r'\$\(', unquoted):
            issues.append(SecurityIssue('COMMAND_SUBSTITUTION'))
        # 检查进程替换  
        if re.search(r'<\(|=\(', unquoted):
            issues.append(SecurityIssue('PROCESS_SUBSTITUTION'))
        # Zsh危险命令
        for cmd in self.ZSH_DANGEROUS:
            if cmd in unquoted.split():
                issues.append(SecurityIssue(f'ZSH_{cmd.upper()}'))
        return issues
```

**P2 - Worktree 隔离**：
```python
# worktree.py
class WorktreeSession:
    def __init__(self, repo_root: str, branch_name: str):
        self.worktree_path = self._create_git_worktree(repo_root, branch_name)
        self.original_cwd = os.getcwd()
    
    def enter(self):
        os.chdir(self.worktree_path)
        clear_system_prompt_cache()
        clear_memory_file_caches()
    
    def exit(self, keep=True):
        os.chdir(self.original_cwd)
        if not keep:
            self._remove_worktree()
```

**P3 - 工具延迟加载**：
```python
# 工具注册时支持 deferred=True
# 只在 tool_search 触发时才注入到系统提示
# 减少默认 prompt 大小

@register_tool(deferred=True, search_hint="web browser fetch URL")
class FetchUrlTool(Tool):
    pass
```

---

## 八、关键安全设计原则

| 原则 | 实现 | 对nutshell的启示 |
|------|------|----------------|
| **多层防御** | 权限模式 + 规则 + 分类器 + 只读验证 | 当前nutshell只有一层 |
| **Fail-closed** | 默认拒绝，需积极证明安全 | 工具接口应默认 is_read_only=False |
| **引用感知** | 提取引用内容，检测引号相邻的危险模式 | 当前pattern检查没有引用感知 |
| **边界保护** | 尾部 `(?=\s\|$)` 防止前缀匹配绕过 | 正则规则需要加边界锚点 |
| **Zsh防御** | ZSH_DANGEROUS_COMMANDS集合 | 需要添加zsh特定的检查 |
| **分类器隔离** | 危险规则在进入auto模式时剥离 | 相关于未来的AI分类模式 |
| **拒绝追踪** | 超过限制时回到交互式 | 防止分类器失败时持续拒绝 |
| **会话隔离** | Plan Mode + Worktree 双重隔离 | Plan Mode对nutshell很有价值 |
