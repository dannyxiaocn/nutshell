# nutshell/tool_engine

负责加载、注册、执行 agent 可调用的工具，包括驱动 skill 加载的内置 `skill` tool。

## 目录结构

```
tool_engine/
├── __init__.py          # 导出 ToolLoader、BashExecutor、SkillExecutor、registry 入口
├── loader.py            # 从磁盘 .json 定义加载 Tool 对象
├── registry.py          # 内置工具注册 + provider swap（bash / skill / web_search）
├── reload.py            # reload_capabilities 元工具，触发 session 热重载
├── sandbox.py           # 已移除（空占位）
└── executor/            # 所有工具的执行实现，按 tool-name/ 分组
    ├── base.py          # BaseExecutor 抽象基类
    ├── skill/           # skill 内置工具：SkillExecutor + create_skill_tool
    ├── terminal/        # 终端命令类工具
    │   ├── bash_terminal.py    # bash 内置工具：BashExecutor + create_bash_tool
    │   └── shell_terminal.py   # agent 创建的 .sh 脚本工具：ShellExecutor
    └── web_search/      # 网络搜索类工具
        ├── brave_web_search.py   # Brave Search 实现（默认）
        └── tavily_web_search.py  # Tavily 实现（备选）
```

## 设计原则

- **executor/ 按 tool-name/ 分组**：每类工具一个子目录，实现与命名一一对应。
- **ToolLoader 只管加载**：把磁盘 `.json + 同名脚本` 转成 `Tool` 对象，不关心业务逻辑。
- **内置工具由 loader + registry 协同处理**：`bash`、`skill`、`web_search` 属于系统内置；agent 自建工具通过 ShellExecutor 执行 `.sh` 脚本，不进注册表。

## 工具来源

| 来源 | 说明 | 执行方式 |
|------|------|----------|
| 系统内置 | `bash`、`skill`、`web_search` | registry / loader → executor/* |
| Agent 创建 | `*.json + *.sh` 磁盘定义 | ShellExecutor（stdin JSON → stdout 结果） |

## 关键文件说明

### `loader.py` — ToolLoader

从 `.json` 工具描述文件加载 `Tool` 对象。Resolution 优先级（高→低）：

1. `impl_registry`（调用方显式注入）
2. `SkillExecutor`（tool_name == "skill"，读取当前 skill 集）
3. `BashExecutor`（tool_name == "bash"）
4. `ShellExecutor`（同名 `.sh` 文件存在）
5. `get_builtin()`（registry 查找）
6. Stub（抛 NotImplementedError）

```python
from nutshell.tool_engine import ToolLoader
tools = ToolLoader(default_workdir=".").load_dir(Path("core/tools"))
```

### `registry.py` — 内置注册 + Provider swap

```python
from nutshell.tool_engine.registry import get_builtin, resolve_tool_impl

impl = get_builtin("bash")          # → BashExecutor callable
impl = get_builtin("skill")         # → create_skill_tool callable
impl = get_builtin("web_search")    # → _brave_search callable

# 切换 web_search 后端
impl = resolve_tool_impl("web_search", "tavily")  # → _tavily_search callable
```

### `executor/skill/skill_tool.py` — skill 工具

- `SkillExecutor`：根据当前 session / entity 已加载的 `Skill` 列表按名称加载 skill
- 返回 skill 正文、base directory 和附属文件提示，便于 skill 继续引用自身目录中的资源

### `executor/terminal/bash_terminal.py` — bash 工具

- `BashExecutor`：subprocess 模式（默认）+ PTY 模式（`pty=true`）
- `create_bash_tool()`：返回封装好 schema 的 `Tool` 对象
- `_venv_env()`：自动激活 session `.venv`（当 `NUTSHELL_SESSION_ID` 存在时）

### `executor/terminal/shell_terminal.py` — agent 创建的 .sh 工具

- `ShellExecutor`：将 kwargs 序列化为 JSON 写入 stdin，执行 `.sh` 脚本，读 stdout 返回

### `executor/web_search/` — 网络搜索

- `brave_web_search.py`：调用 Brave Search API（需 `BRAVE_API_KEY`）
- `tavily_web_search.py`：调用 Tavily API（需 `TAVILY_API_KEY`，备选）

### `reload.py` — reload_capabilities 元工具

持有 Session 引用，调用时触发 `session._load_session_capabilities()`，让 agent 在不重启的情况下感知 `core/tools/` 和 `core/skills/` 的文件变化。由 `runtime/session.py` 强制注入，不经过磁盘加载。

```python
from nutshell.tool_engine.reload import create_reload_tool
reload_tool = create_reload_tool(session)  # session 提供 _load_session_capabilities()
```

## 依赖关系

- 依赖 `nutshell.core.Tool`、`BaseLoader` 抽象
- 被 `nutshell.runtime.session.Session` 调用：加载 `core/tools/`、替换 bash executor
- `executor/terminal/bash_terminal.py` 读取 `NUTSHELL_SESSION_ID` 环境变量以激活 session venv
