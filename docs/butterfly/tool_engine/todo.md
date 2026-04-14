# Tool Engine — Todo

## Completed

- [x] Tool-level sandbox redesign: ToolSandbox base, BashSandbox, WebSandbox, FSSandbox (4a48ad3)
- [x] WebSandbox: domain blacklist + response truncation (ec90b69, 2d49425)
- [x] Token calculator tool: count_tokens(text, model) (cb43c19)
- [x] Web search: Brave + Tavily multi-provider
- [x] Hot reload via reload_capabilities

## Future

### Minimal Parameter Design — Next Iterations

- [ ] **CLI app tool auto-auth**: 当 agent 调用外部 CLI 工具（gh, gcloud, aws, npm 等）时，runtime 应自动注入认证信息（token, API key, session cookie），agent 只传业务参数。实现路径：executor 构造时读取 `~/.butterfly/credentials/` 或 session-level credential store，注入到 env vars 或 CLI flags
- [ ] **File context auto-resolve**: agent 引用 session 内文件时只传相对路径（`core/memory/notes.md`），tool executor 自动 resolve 为绝对路径并校验不越界
- [ ] **Tool output auto-truncation policy**: 每个 tool 在 `tool.json` 中声明 `max_output` 策略（bytes/lines/summary），runtime 自动截断，agent 无需传 `max_output` 参数
- [ ] **Session env auto-injection**: 所有 toolhub executor 自动继承 session 环境变量（`BUTTERFLY_SESSION_ID`, `BUTTERFLY_ENTITY`, venv `PATH`），不需要每个 executor 单独处理
- [ ] **Multi-step tool auth flow**: 对需要 OAuth/interactive login 的工具，runtime 代理完成 auth flow（浏览器 redirect → token capture → credential store），agent 侧完全透明
- [ ] **Per-tool rate limiting**: runtime 层面按 tool name 限速（如 web_search 每分钟 N 次），超限时自动排队而非报错，agent 无感知

### Other

- [ ] Sandbox enforcement beyond placeholders
- [ ] Tool usage analytics integration
- [ ] ToolHub hot-add: 支持运行时向 toolhub/ 添加新工具并通过 `reload_capabilities` 生效
- [ ] Tool dependency declaration: tool.json 声明依赖的系统命令或 Python 包，session init 时自动检查/安装
