# Nutshell 使用日志

记录用 Nutshell（主要通过 nutshell-chat + kimi_agent）执行各类任务的过程。
- **好的** → 记录下来强化
- **不好的** → 记录为 bug 或 UX 问题，立即实现修复
- **想要但没有的** → 记为 TODO，一定要开发，不绕过

---

## 规则

1. 每次使用都记一条
2. 遇到 missing feature → 立即加入 TODO，下次实现
3. 不允许 workaround，只允许实现

---

## 日志条目

<!-- 格式：
### YYYY-MM-DD — <任务描述>
**Session**: `<session_id>`  **Entity**: `<entity_name>`
**做了什么**: ...
**好的**: ...
**问题**: ...
**Missing / TODO**: ...
-->

### 2026-03-25 — nutshell-chat 首次测试运行
**Session**: `2026-03-25_09-24-03`, `2026-03-25_09-24-56`  **Entity**: `agent`
**做了什么**: 尝试 `nutshell-chat --timeout 30 "用一句话介绍你自己"`
**发现的 bug**:
1. **AgentLoader 调用错误** — `AgentLoader(entity_base).load(entity_name)` 将 `entity_base` 误传给 `impl_registry` 参数，导致 `agent.yaml not found`。已修复（commit `82a4b9d`）。
2. **SOCKS proxy 干扰** — `all_proxy=socks5://127.0.0.1:7890` 导致 `socksio package not installed` 错误。需 unset `all_proxy` 或安装 `socksio`。
3. **API key 未设置** — 测试环境 `ANTHROPIC_API_KEY` 未配置，daemon 收到 auth error。
**好的**: session 目录正确创建，events.jsonl 清楚记录了错误原因，user_input 写入成功。
**Missing / TODO**: `nutshell-chat` 应支持 `.env` 文件自动加载（同目录或项目根）

---

## TODO（来自使用中发现的 missing features）

<!-- 实现后划掉 -->
- [ ] **`.env` 文件自动加载** — `nutshell-chat` 应在启动时自动寻找并加载 `.env` 文件，避免用户必须手动 `export` API key。

