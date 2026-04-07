# nutshell/core

一句话定位：定义 agent 运行时依赖的核心抽象与主循环，包括 Agent、Tool、Skill、Provider 和基础数据类型。

## 文件列表
- `__init__.py`：导出核心公共 API（`Agent`、`Tool`、`tool`、`Skill`、`Provider`、类型对象）。
- `agent.py`：Agent 主执行循环；组装 system prompt、调用 provider、执行工具、维护 history 与 token 统计。
- `hook.py`：定义运行时钩子类型别名（文本流、tool call、loop start/end 等回调）。
- `loader.py`：通用 `BaseLoader[T]` 抽象，供 skill/tool loader 复用。
- `provider.py`：LLM provider 协议；约定 `complete()` 的输入输出与流式行为。
- `skill.py`：`Skill` 数据模型；支持文件型 skill 与内联 skill。
- `tool.py`：`Tool` 封装、`@tool` 装饰器、从 Python 注解推导 JSON Schema。
- `types.py`：消息、工具调用、token 统计、AgentResult 等基础类型。

## 关键设计 / 架构说明
- `Agent` 只负责推理循环与 prompt 组织，不直接关心会话目录、文件系统或 UI；会话态注入由 runtime 层完成。
- system prompt 被拆成 `static_prefix` 与 `dynamic_suffix`，为支持 provider 侧 prompt cache 做准备。
- memory、memory layers、app notifications、skills 都作为可插拔输入拼接进 prompt，而不是写死在 provider 层。
- `Tool` 统一暴露为 JSON-schema-compatible API；函数既可同步也可异步，调用方无需区分。
- `Provider` 以协议定义最小能力面，core 不耦合具体厂商实现。

## 主要对外接口
### `class Agent`
典型用法：
```python
from nutshell.core import Agent
from nutshell.llm_engine.registry import resolve_provider

agent = Agent(provider=resolve_provider('anthropic'), model='claude-sonnet-4-6')
result = await agent.run('hello')
print(result.content)
```
关键参数/方法：
- `Agent(...)`：注入 provider、model、tools、skills、system prompt 等。
- `await agent.run(input, clear_history=False, ..., caller_type='human')`：执行一次 agent loop。
- `agent.close()`：清空历史。

### `class Tool`
```python
from nutshell.core import Tool

tool = Tool(name='echo', description='Echo text', func=lambda text: text)
text = await tool.execute(text='hi')
```
- `execute(**kwargs)`：执行工具。
- `to_api_dict()`：转成 provider 需要的 tool schema。

### `@tool` 装饰器
```python
from nutshell.core import tool

@tool(description='Add two numbers')
def add(a: int, b: int) -> int:
    return a + b
```
- 自动生成 `Tool` 实例和 schema。

### `class Skill`
- 用于承载 skill 元数据和正文；通常由 `skill_engine.loader.SkillLoader` 创建。

### `class Provider`
- provider 实现需提供：
```python
async def complete(...)-> tuple[str, list[ToolCall], TokenUsage]
```

## 与其他模块的依赖关系
- 被 `nutshell.runtime` 依赖：runtime 创建 Session，并把 prompts / memory / tools / skills 注入 `Agent`。
- 被 `nutshell.skill_engine` 依赖：`SkillLoader` 产出 `Skill`，`renderer` 渲染 skill block。
- 被 `nutshell.tool_engine` 依赖：`ToolLoader` 和内置 tool 注册都基于 `Tool` 抽象。
- 被 `nutshell.llm_engine` 依赖/实现：具体 provider 实现 `Provider` 协议并被 Agent 调用。
