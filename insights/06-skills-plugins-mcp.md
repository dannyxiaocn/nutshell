# Claude Code 技能系统、插件架构与 MCP 集成 — 深度分析

## 执行摘要

Claude Code 包含三个互相协作但独立的扩展系统：
- **Skills**（技能）：MCP 风格的 markdown 提示命令，支持参数替换、工具白名单、文件路径过滤、钩子
- **Plugins**（插件）：自包含的 npm 包，可提供多个技能、工具、MCP 服务器
- **MCP**（Model Context Protocol）：标准化工具协议，通过多种传输（stdio/HTTP/WebSocket）连接

核心创新点是 **ToolSearchTool 的延迟加载机制**，通过 `shouldDefer` 和 `alwaysLoad` 标记实现按需加载大量工具。

---

## 一、Skills 系统设计

### 1.1 格式规范（SKILL.md）

Skills 遵循 **Agent Skills 规范**，结构为 YAML 前置元数据 + Markdown 主体：

```markdown
---
name: skill-name
description: "When and why to use this skill"
whenToUse: "Detailed scenarios for skill activation"
argumentHint: "arg1, arg2"
allowedTools: ["Read", "Bash", "Edit"]      # 工具白名单
model: "claude-3-5-sonnet-20241022"          # 可选：模型覆盖
paths: ["src/**", "tests/**"]               # 可选：文件路径过滤
effort: "5"                                  # 可选：用户感知工作量
version: "1.0.0"
hooks:                                       # 可选：注册钩子
  pre_command:
    - run: "echo starting"
---

# Skill Content

实际的 Markdown 正文会在技能调用时注入到 prompt 中。
支持参数替换：{file_path}、{user_input} 等占位符。
```

**关键字段**：
- `name`：技能标识符（用于 `/skill-name` 命令）
- `description`：模型用于判断是否加载该技能的激活触发器
- `whenToUse`：详细的使用场景描述
- `allowedTools`：该技能可以访问的工具白名单
- `paths`：glob 模式，涉及匹配文件后才显示该技能

### 1.2 加载机制

**文件系统发现**（`loadSkillsDir.ts`）：
1. 扫描 `skills/` 目录查找 `SKILL.md` 或 `.md` 文件
2. 使用 `parseFrontmatter()` 提取 YAML 元数据
3. 调用 `parseSkillFrontmatterFields()` 规范化字段
4. 创建 `Command` 对象（`type: 'prompt'`）
5. **估算 frontmatter token 成本**（用于上下文预算）

**内置技能注册**（`src/skills/bundled/`）：
```typescript
registerBundledSkill({
  name: 'remember',
  allowedTools: ['Read', 'Bash'],
  getPromptForCommand: async (args, context) => { ... },
  files?: {
    'template.txt': '...',
    'examples/case1.md': '...'
  }
})
// 文件在首次调用时延迟提取到 ~/.claude/bundled-skills/{name}/
// 使用 Memoization 防止并发冲突
```

### 1.3 触发条件与 Prompt 注入

**模型何时看到技能**：
- 通过 `formatCommandsWithinBudget()` 渲染为简洁列表
- **总 Token 预算**：上下文窗口的 1%（可配置）
- **单条最大长度**：250 字符
- Bundled 技能优先保留
- 技能内容不会全量注入 prompt，只注入 name + description + whenToUse

**文件路径过滤**：
```
paths: ["src/**", "tests/**"]
→ 只有当对话涉及匹配文件时，才向模型展示该技能
→ 使用 ignore 库进行 GITIGNORE 风格匹配
```

### 1.4 执行模式

- **Inline 执行**（默认）：skill 内容展开到当前对话
- **Fork 执行**（子代理）：创建隔离的子代理（独立 token 预算），用于资源密集型操作

---

## 二、Plugin 系统架构

### 2.1 插件格式

插件是自包含的 npm 包或目录：

```
my-plugin/
├── package.json
├── manifest.json
├── skills/
│   ├── reasoning/SKILL.md
│   └── coding/SKILL.md
├── tools/
│   ├── CustomTool.json
│   └── custom_tool.sh
├── mcp-servers/
│   └── my-server-config.json
└── hooks.js
```

### 2.2 插件生命周期

**安装流程**（`PluginInstallationManager`）：
1. 验证插件元数据（marketplace 或本地）
2. 解析版本号，下载/本地化包
3. 验证 manifest.json
4. 提取到版本控制路径：`~/.claude/plugins/@marketplace/my-plugin/v1.0.0/`
5. 记录在 `installed_plugins.json`
6. 加载技能、工具、MCP 配置
7. 添加到 `settings.json:enabledPlugins`

**作用域**：

| 作用域 | 路径 | 说明 |
|--------|------|------|
| `user` | `~/.claude/plugins/` | 全局 |
| `project` | `.claude/plugins/` | 当前项目仅 |
| `managed` | 系统管理 | 只读 |
| `bundled` | 编译到 CLI | 内置 |

### 2.3 内置插件

通过 `registerBuiltinPlugin()` 注册，可提供 skills、MCP 服务器、钩子，支持条件可用性（`isAvailable()` + feature flags）。

---

## 三、MCP（Model Context Protocol）集成

### 3.1 服务器配置

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "node",
      "args": ["./index.js"]
    },
    "brave": {
      "type": "http",
      "url": "https://api.search.brave.com/mcp",
      "oauth": { "clientId": "...", "authServerMetadataUrl": "..." }
    }
  }
}
```

**支持的传输**：stdio、SSE、HTTP、WebSocket、SDK、Claude.ai 代理

### 3.2 工具注册与调用

**连接生命周期**：
1. 初始化 MCPConnectionManager
2. 从配置加载所有 MCP 服务器
3. 连接到每个服务器
4. 列举工具与提示（ListTools、ListPrompts）
5. 转换为 Claude Code 命令（标准化工具名）

**工具名标准化**：
- MCP 工具名：`mcp__github__search_repos`
- 格式：`server__action`
- 反向：`normalizeNameForMCP()` 提取 serverName 和 toolName

**工具执行流程**：
```
模型调用 → MCPTool.call() → 可能触发 OAuth → 执行
→ 截断结果（> 100K 字符时持久化到文件）
```

### 3.3 MCP Skills（MCP 提示）

MCP 服务器可通过 `ListPrompts` 提供 Skills。Claude Code 将其转换为 `Command` 对象（`loadedFrom: 'mcp'`），在 SkillTool 列表中选择性包含。

---

## 四、ToolSearchTool 延迟加载机制

### 4.1 核心标记

```typescript
interface Tool {
  readonly shouldDefer?: boolean    // 延迟加载，不进入初始 prompt
  readonly alwaysLoad?: boolean     // 始终显示（即使 shouldDefer 为 true）
}
```

**加载优先级**：
1. `alwaysLoad: true` → 始终显示
2. `isMcp: true` → 总是延迟（除非 alwaysLoad）
3. `shouldDefer: true` → 延迟
4. 否则 → 正常显示

**始终不延迟的工具**：
- ToolSearchTool 本身
- Brief 工具（通信通道）
- AgentTool（Fork-first）
- 任何 `alwaysLoad: true` 的工具

### 4.2 搜索流程

**阶段 1**：发现延迟工具列表
```
deferredTools = tools.filter(t => isDeferredTool(t))
→ ['mcp__github__search', 'mcp__brave__web_search', ...]
```

**阶段 2**：模型调用 ToolSearchTool
```
query: "select:mcp__github__search"  # 精确选择
  或   "notebook jupyter"             # 关键字搜索
→ parseToolName() 解析 → buildSearchResult() → 返回完整 JSONSchema
```

**阶段 3**：关键字搜索计分
- 完全名称匹配 → 最高分
- 单词匹配 → 高分
- 描述匹配 → 中等分

### 4.3 延迟加载的好处

| 优势 | 说明 |
|------|------|
| **小初始 Prompt** | 减少 token，特别是 MCP 工具众多时 |
| **快首次 API 调用** | 无需等待所有工具架构加载 |
| **工作流优化** | 模型只看到相关工具 |
| **缓存友好** | 新 MCP 工具不失效系统 prompt 缓存 |

---

## 五、对 Nutshell 的改进建议

### 现状对比

| 功能 | Claude Code | Nutshell 当前 | 改进方向 |
|------|------------|-------------|--------|
| Skill 参数替换 | `{file_path}` 占位符 | 无 | 添加参数替换 |
| 工具白名单 | `allowedTools: [...]` | 无 | 运行时验证 |
| 文件路径过滤 | `paths: ["src/**"]` | 无 | 动态可见性 |
| 生命周期钩子 | `pre_command`, `post_command` | 无 | 触发点支持 |
| Skill token 预算 | 上下文的 1%，250字符/条 | 无限制 | 实现预算约束 |
| 模型覆盖 | `model: "..."` per skill | 无 | 按 skill 切换模型 |
| 插件系统 | npm 包 + marketplace | entity/skills/ 目录 | 可参考版本化机制 |
| MCP 集成 | 完整协议支持 | 无 | 可接入标准工具 |
| 工具延迟加载 | `shouldDefer` + ToolSearch | 无 | 减少 prompt 大小 |

### 具体改进方案

**P0 - Skill 参数替换**：
```python
# nutshell/skill_engine/renderer.py
def substitute_skill_args(skill_content: str, args: dict) -> str:
    """Replace {param_name} placeholders in skill body."""
    result = skill_content
    for name, value in args.items():
        result = result.replace(f"{{{name}}}", str(value))
    return result

# SKILL.md 格式扩展
# ---
# name: code-review
# argumentHint: "file_path, focus_area"
# ---
# Review {file_path} focusing on {focus_area}...
```

**P1 - Skill Token 预算约束**：
```python
# 避免技能列表占用过多 prompt 空间
MAX_SKILL_CATALOG_TOKENS = context_window * 0.01  # 1%
MAX_SKILL_ENTRY_CHARS = 250  # 每条技能的最大字符数

def build_skills_block(skills, context_window):
    budget = int(context_window * 0.01)
    result = []
    for skill in prioritize_skills(skills):
        entry = format_skill_entry(skill)[:MAX_SKILL_ENTRY_CHARS]
        if estimate_tokens(entry) > budget:
            break
        result.append(entry)
        budget -= estimate_tokens(entry)
    return "\n".join(result)
```

**P1 - 工具白名单（allowedTools）**：
```python
# 在 SKILL.md frontmatter 中声明
# allowed_tools: [bash, web_search]

# 在 Session._load_session_capabilities() 中
if skill.allowed_tools:
    available_tools = [t for t in all_tools if t.name in skill.allowed_tools]
else:
    available_tools = all_tools
```

**P1 - 工具延迟加载**：
```python
# 在工具注册时设置
@register_tool(deferred=True, search_hint="fetch URL content from web")
class FetchUrlTool(Tool):
    pass

# 非延迟工具（总是加载）
@register_tool(deferred=False)
class BashTool(Tool):
    pass

# 在 _load_session_capabilities() 中
always_loaded = [t for t in tools if not t.deferred]
deferred = [t for t in tools if t.deferred]

# 将 ToolSearchTool 注入 always_loaded
# 将 deferred 工具名列表注入 system prompt
# 模型通过 ToolSearchTool 按需激活
```

**P2 - 文件路径过滤**：
```python
# SKILL.md frontmatter
# paths: ["src/**", "*.py"]

import pathspec

def should_show_skill(skill, conversation_files: list[str]) -> bool:
    if not skill.paths:
        return True
    spec = pathspec.PathSpec.from_lines("gitwildmatch", skill.paths)
    return any(spec.match_file(f) for f in conversation_files)
```

---

## 六、关键设计原则

1. **技能是提示模板，不是代码**：SKILL.md 只是 Markdown，降低创建门槛
2. **延迟加载保持 prompt 精简**：大量 MCP 工具不影响初始 prompt 大小
3. **Token 预算约束技能目录**：防止技能过多撑爆 context window
4. **文件路径过滤提高相关性**：只在相关场景下展示技能，减少干扰
5. **插件系统版本隔离**：`v1.0.0` 目录隔离，升级不破坏旧版本
6. **MCP 统一工具命名**：`server__action` 格式避免命名冲突

---

## 七、系统关系图

```
Skills ←── Plugin ──→ MCP 服务器
  ↑           ↑           ↓
  │           │      工具注册
  │      Marketplace
  │
prompt 注入
  ↓
ToolSearchTool（延迟加载网关）
  ↓
deferred 工具（MCP 工具、特殊工具）
```
