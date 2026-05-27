# COURSE_AGENT

## 项目定位

这是一个围绕课程作业、代码任务、多 Agent 编排与图式运行时持续演进的 Agent 平台样板。

## 当前技术栈

- Python
- Typer CLI
- Chainlit UI
- LangGraph
- OpenAI-compatible LLM provider

## 工程约束

- 优先小步、最小侵入修改
- 优先复用现有 runtime / graph / session 能力
- 变更后优先运行 targeted tests，再跑全量 pytest / ruff

## Prompt 约束

- 采用 static prefix + dynamic tail 分层
- 静态前缀保持稳定、共享、可缓存
- 动态尾部纳入环境、项目说明、session、任务上下文

## 分享重点

- agent loop
- graph-native runtime
- stateful session
- prompt architecture
