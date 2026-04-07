# nutshell/tool_engine

一句话定位：负责加载、注册、执行并约束 agent 可调用的工具，包括磁盘工具定义、内置 provider 工具与 sandbox。

## 文件/子目录列表
- `__init__.py`：导出 `ToolLoader` 与内置工具注册入口。
- `loader.py`：从 `.json` 工具描述和同名脚本加载 Tool；支持 shell/bash 等 executor。
- `registry.py`：注册与解析内置工具实现，以及按 provider key 选择实现。
- `reload.py`：生成 `reload_capabilities` 内置工具，触发 session 热重载。
- `sandbox.py`：工具调用前检查与结果过滤；包含通用、bash、文件系统、web sandbox。
- `executor/`：脚本型工具执行后端。
  - `__init__.py`：导出 executor 类型。
  - `base.py`：`Executor` 抽象协议。
  - `bash.py`：bash 命令执行器。
  - `shell.py`：通用 shell 脚本执行器。
- `providers/`：内置 Python 工具实现。
  - `app_notify.py`：管理 `core/apps/*.md` 持久通知。
  - `archive_session.py`：归档 session 到 `_archived/`。
  - `count_tokens.py`：按模型估算/统计 token。
  - `entity_update.py`：提交 entity / parent entity 更新提案。
  - `fetch_url.py`：抓取 URL 文本内容。
  - `get_session_info.py`：读取 session 元数据、近期 turn、tasks、memory 列表。
  - `git_checkpoint.py`：在仓库内做 checkpoint commit。
  - `list_child_sessions.py`：列出当前 entity 的子 session。
  - `load_skill.py`：按名称加载 skill 正文。
  - `recall_memory.py`：检索 session memory。
  - `session_msg.py`：向其他 session 发送同步/异步消息。
  - `spawn_session.py`：动态创建新 session。
  - `state_diff.py`：保存状态快照并返回 diff。

## 关键设计 / 架构说明
- 工具来源分两类：
  - 磁盘定义工具：`*.json + 同名脚本`，适合 entity/session 自定义。
  - 内置 provider 工具：Python 实现，适合运行时能力与系统级操作。
- `ToolLoader` 只负责把文件定义转成 `Tool`；实际 provider 绑定、sandbox 注入由 runtime 层完成。
- executor 层把“脚本如何执行”与“工具如何描述”分离，便于统一 shell/bash 工具加载。
- sandbox 分为输入检查和输出过滤两步，既可拦危险命令，也可裁剪超长结果。
- `reload_capabilities` 不从磁盘加载，而是由 runtime 强制注入，保证任何 session 都能热更新能力。

## 主要对外接口
### `class ToolLoader`
```python
from pathlib import Path
from nutshell.tool_engine import ToolLoader

loader = ToolLoader(default_workdir='.')
tool = loader.load(Path('tools/bash.json'))
tools = loader.load_dir(Path('tools'))
```
- `load(path)`：加载单个工具定义。
- `load_dir(directory)`：批量加载目录中的工具。

### `get_builtin(name)` / `resolve_tool_impl(...)` in `registry.py`
```python
from nutshell.tool_engine.registry import get_builtin, resolve_tool_impl
impl = get_builtin('spawn_session')
```
作用：获取内置工具实现或按 provider key 解析实现。

### `create_reload_tool(session)`
```python
from nutshell.tool_engine.reload import create_reload_tool
reload_tool = create_reload_tool(session)
```
作用：创建 `reload_capabilities` 工具。

### Sandbox 类
```python
from nutshell.tool_engine.sandbox import BashSandbox, WebSandbox
```
- `check(tool_name, params)`：拦截危险调用。
- `filter_result(tool_name, result)`：裁剪输出。

### Executor 类
```python
from nutshell.tool_engine.executor.bash import BashExecutor
result = await BashExecutor(workdir='.').execute(command='ls -la')
```

## 与其他模块的依赖关系
- 依赖 `nutshell.core.Tool`、`BaseLoader` 抽象。
- 被 `nutshell.runtime.session.Session` 调用：加载 session `core/tools/`、注入 sandbox、替换特定实现。
- 与 `entity/agent/tools/*.json`、`sessions/*/core/tools/` 的工具定义格式直接绑定。
- 部分 provider 工具依赖 `nutshell.runtime`（如 session factory、entity update、status/目录结构）。
- 被测试目录 `tests/tool_engine/` 重点覆盖。
