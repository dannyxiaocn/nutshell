# Claude Code Prompt 工程和上下文管理 — 深度分析

## 概述

Claude Code 是一个复杂的 LLM agent 框架，包含精细化的 prompt 工程、上下文管理和缓存优化机制。核心在 `src/query.ts`（1729行）和 `src/services/api/claude.ts`（3419行）。

---

## 一、Query 层：LLM 请求构建与发送

### 消息格式和上下文注入策略

**query() 函数** 是异步生成器，实现完整查询循环：
- **输入**：`QueryParams` 包含 messages、systemPrompt、userContext、systemContext、toolUseContext
- **消息归一化**：通过 `normalizeMessagesForAPI()` 清理消息格式，处理思维块、工具结果配对
- **上下文注入时机**：
  1. **用户上下文**：`prependUserContext()` 插入系统提醒块到消息头部（`<system-reminder>` 标签）
  2. **系统上下文**：`appendSystemContext()` 追加到系统提示末尾
  3. **工具搜索**：动态在消息中注入发现的工具名称

**消息处理管道**：
```
输入消息 → 过滤重复 → 归一化格式 → 验证工具结果配对
→ 插入系统上下文 → 性能检查点 → 发送 API
```

**关键特征**：
- 支持工具结果摘要（`ToolUseSummaryMessage`）压缩历史
- 自动故障恢复（max_output_tokens 错误自动重试最多3次）
- 支持 task_budget（API 侧出力预算追踪）

---

## 二、系统 Prompt 构建策略

### 分阶段注入和顺序

**Claude Code 的构建顺序**（constants/prompts.ts）：

1. **固定导出块**：
   - 简介（"You are an interactive agent..."）
   - 系统规则（工具、上下文窗口自动压缩）
   - 行动指南（可逆性、风险评估）
   - 任务指导（软件工程专项指导）

2. **工具部分**：
   - 工具清单与权限系统说明
   - MCP 指令（如果启用）
   - 代理工具和发现指导

3. **会话特定部分**（SYSTEM_PROMPT_DYNAMIC_BOUNDARY 之后，不缓存）：
   - 技能发现（如果可用）
   - 语言偏好
   - 输出风格（Markdown/结构化）
   - 代理协作模式指导

4. **动态内存部分**（不缓存）：
   - 会话记忆
   - 内存层（>60行截断）
   - 应用通知

### 长度控制策略

- **内存层截断**：>60行的内存文件只注入前60行 + `"... (N 行被省略，完整内容: cat core/memory/<name>.md)"` 提示
- **内存分层渐进式公开**：大文件通过 bash 指令让模型按需读取
- **工具提示懒加载**：工具描述缓存在会话级别，避免每次重新计算

---

## 三、Prompt Caching 机制

### cache_control 设置策略

**分两个边界的多段缓存**（`src/services/api/claude.ts`）：

```typescript
// buildSystemPromptBlocks() 分割系统提示成可缓存块
splitSysPromptPrefix(systemPrompt) → [
  { text: "billing-header", cacheScope: null },          // 不缓存
  { text: "system.md prefix", cacheScope: null },        // 不缓存（变动）
  { text: "static content before boundary", cacheScope: 'global' }, // 全局缓存
  { text: "dynamic content after boundary", cacheScope: null }       // 不缓存
]
```

**三种缓存模式**：

1. **全局缓存（1P only）**：
   - 使用 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 标记分界
   - 前部分：`scope: 'global'`（跨组织缓存）
   - 后部分：`scope: null`（不缓存）
   - 条件：shouldUseGlobalCacheScope() && 无 MCP 工具

2. **组织级缓存（3P/MCP）**：
   - 使用 `scope: 'org'`
   - 用于 Bedrock/Vertex/代理

3. **1h TTL 优化**（高频短会话）：
   - 条件：`getFeatureValue('tengu_prompt_cache_1h_config')`
   - 仅限 Ant/Claude.ai 订阅者
   - 按 querySource 允许列表（支持前缀匹配，如 `'repl_main_thread*'`）

**缓存失效机制**：
- 系统提示分界改变 → 新的 cache_control 布局 → 缓存键变化
- `/clear` 或 `/compact` 命令 → `clearSystemPromptSections()`
- 动态部分（内存）变化 → cacheBreak=true 的部分重新计算
- `should1hCacheTTL()` 在会话启动时 latch，防止中途 GrowthBook 更新导致 TTL 翻转

---

## 四、autoDream：后台自主内存整理

### 触发条件（三重门闩）

1. **时间门闩**：距上次整理 ≥ minHours（默认24h）
2. **会话门闩**：距上次整理后的新会话 ≥ minSessions（默认5个）
3. **扫描节流**：防止频繁扫描（10分钟间隔）

### 执行流程

1. 获取内存根目录和会话目录
2. 构建 `consolidationPrompt(memoryRoot, transcriptDir, extra)`
3. 以 forked agent 执行（不进入主转录）
4. **工具限制**：仅读取 bash（ls、find、grep、cat 等）
5. 跟踪修改的文件路径，更新 DreamTask 状态
6. 记录缓存读/创建使用量到 analytics

**与 compact 的区别**：
- compact：单次会话内压缩上下文
- autoDream：跨会话的长期内存整理（向量化、去重、汇总）

---

## 五、thinkback：会话可视化回顾

**thinkback** 是一个 plugin/skill 集合（而非核心 agent 功能）：

**工作流**：
1. 运行 `/think-back` skill
2. 调用 API 生成 `year_in_review.js` 数据
3. `playAnimation()` 运行 node player.js 生成 HTML
4. 在浏览器中打开可视化结果

**用途**：用户主动触发的年度/历史对话可视化，与 autoDream 的自动整理不同。

---

## 六、ultraplan：远程多轮规划助手

**ultraplan** 是运行在 CCR（Claude Code Remote）上的规划器：

```typescript
buildUltraplanPrompt(blurb: string, seedPlan?: string): string
// 可选种子计划 + 指令 + 用户描述

// 执行模式
executeMode: 'remote' | 'local'  // CCR CLI 或本地 CLI
timeout: 30分钟                   // 多代理探索耗时
exitCondition: pollForApprovedExitPlanMode()  // 等待用户批准计划
```

**与 agent tool 的对比**：
- ultraplan：面向大规模多轮研究/规划的专用模式，在远端运行
- agent tool：一般多代理编排，本地运行

---

## 七、Context Window 使用统计

### 令牌计数
```typescript
getTokenCountFromUsage(usage: Usage): number
  = input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens

finalContextTokensFromLastResponse(messages): number
  // 从最后 API 响应提取最终窗口大小
  // 用于 task_budget.remaining 跨压缩边界追踪
```

### 统计埋点
```typescript
logEvent('tengu_sysprompt_block', {
  snippet: firstSystemPrompt.slice(0, 20),
  length: firstSystemPrompt.length,
  hash: sha256(firstSystemPrompt)  // 监控 prompt 变化
})

logEvent('tengu_sysprompt_boundary_found', {
  blockCount, staticBlockLength, dynamicBlockLength
})
```

---

## 八、对 Nutshell 的改进建议

### 现状对比

| 模式 | Claude Code | Nutshell | 状态 |
|------|------------|---------|------|
| Prompt 分段（静态+动态） | ✓ | ✓ 已实现 | 一致 |
| 内存层截断（>60行） | ✓ | ✓ 已实现 | 一致 |
| SYSTEM_PROMPT_DYNAMIC_BOUNDARY | ✓ 全局缓存边界 | ✗ 缺失 | 可改进 |
| cache_control scope（global/org） | ✓ | 只有 ephemeral | 可改进 |
| 1h TTL 优化 | ✓ querySource许可列表 | ✗ | 可选 |
| autoDream（跨会话整理） | ✓ 三重门闩触发 | ✗ | 可增加 |

### 改进方案

**P1 - 引入 SYSTEM_PROMPT_DYNAMIC_BOUNDARY 标记**：
```python
SYSTEM_PROMPT_DYNAMIC_BOUNDARY = "\n\n<!-- dynamic-boundary -->\n\n"

def _build_system_parts(self) -> tuple[str, str]:
    """返回 (可缓存静态前缀, 不缓存动态后缀)"""
    static_parts = [self.system_prompt, self.session_context]
    static_block = "\n\n".join(filter(None, static_parts))
    
    dynamic_parts = []
    # memory, layers, skills...
    dynamic_block = "\n\n".join(filter(None, dynamic_parts))
    
    return static_block, dynamic_block
```

在 AnthropicProvider 中：
```python
# 使用两个分开的 cache_control 块
messages_param = [
    {
        "type": "text",
        "text": static_block,
        "cache_control": {"type": "ephemeral"}  # 或 scope: "global"
    },
    {
        "type": "text",
        "text": dynamic_block
        # 无 cache_control
    }
]
```

**收益**：支持全局缓存作用域（跨会话重用静态系统提示，降低成本）

**P1 - cache_control scope 支持**：
```python
# 在 AnthropicProvider.complete() 中
def _build_system_blocks(self, static: str, dynamic: str) -> list[dict]:
    blocks = []
    if static:
        blocks.append({
            "type": "text",
            "text": static,
            "cache_control": {
                "type": "ephemeral",
                # 如果是 1P Anthropic 且无 MCP：
                "scope": "global" if self._use_global_cache() else "org"
            }
        })
    if dynamic:
        blocks.append({"type": "text", "text": dynamic})
    return blocks
```

**P2 - autoDream（跨会话内存整理）**：
```python
# 参考 CC 的三重门闩触发
class AutoDream:
    MIN_HOURS = 24
    MIN_SESSIONS = 5
    
    def should_run(self) -> bool:
        hours_since = (time.time() - self.last_run_ts) / 3600
        sessions_since = self.count_sessions_since_last_run()
        return hours_since >= self.MIN_HOURS and sessions_since >= self.MIN_SESSIONS
    
    async def run(self, memory_root: Path):
        """Forked agent consolidates memory files"""
        # 工具限制：只读 bash + 只写 memory/
        pass
```

**P2 - 基于 token 的上下文预警**：
```python
# 在每次 complete() 后检查 context 使用率
def check_context_health(usage: TokenUsage, context_window: int):
    used = usage.input_tokens + usage.cache_read
    ratio = used / context_window
    if ratio >= 0.95:
        emit_event("context_near_limit", {"ratio": ratio, "action": "compact"})
    elif ratio >= 0.75:
        emit_event("context_warning", {"ratio": ratio})
```

---

## 九、关键设计原则总结

1. **分界标记分离缓存区域**：SYSTEM_PROMPT_DYNAMIC_BOUNDARY 让静态内容全局缓存，动态内容每次重算
2. **门闩设计防止过度触发**：时间门闩 + 会话门闩 + 节流，三重保护 autoDream 不浪费
3. **故障恢复内置**：max_output_tokens 错误自动重试，不暴露给上层
4. **缓存键稳定性**：会话启动时 latch TTL 配置，防止 GrowthBook 中途更新导致缓存失效
5. **工具分类减少 prompt 长度**：shouldDefer=true 的工具不进入主 prompt，按需通过 ToolSearch 激活
