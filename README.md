# 📚 Course Agent

> **面向学生课程作业场景的智能 Agent 系统** —— 不只是和 AI 聊天，而是让 AI 像助教一样「动手」帮你完成作业。

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](#-python-版本要求)
[![Status](https://img.shields.io/badge/Milestone%201-complete-brightgreen.svg)](#-当前进度)
[![UI](https://img.shields.io/badge/UI-Chainlit%20Web-ff4b4b.svg)](#3-启动方式)

---

## 🎯 这是什么？和传统「AI 聊天」有什么区别？

**一句话**：传统 AI 聊天是「你问它答」，Course Agent 是**「你给任务，它自己决定要用什么工具、分几步完成，最后交回结果」**。

### 直观对比

| 维度 | 📱 普通 AI Chat（ChatGPT 网页版 / 文心 / 通义等） | 🤖 Course Agent |
|---|---|---|
| **核心范式** | 单轮 prompt → response | **ReAct Agent Loop**：思考 → 调用工具 → 观察结果 → 继续思考 |
| **能否调用外部能力** | ❌ 只能输出文本 | ✅ 自动调用 `calculator`、`file_read/write`、`web_search`（Tavily/DDG 真实联网）、`web_fetch`、`recall`/`remember`（语义记忆）等工具 |
| **数值计算是否靠谱** | ❌ 可能"编造"计算结果 | ✅ 遇到算式**强制走 calculator**，AST 安全求值，杜绝幻觉 |
| **能不能读写本地文件** | ❌ 做不到 | ✅ `file_read` 直接读作业 PDF/py/txt，`file_write` 把答案保存到文件 |
| **跨会话记忆** | ⚠️ 仅同一会话/部分付费版云端记忆 | ✅ **本地 Chroma 向量库**：上次说"我喜欢 Python"，下次新会话也能 `recall` 出来 |
| **是否能扩展新工具** | ❌ 用户无法自定义 | ✅ `@tool` 装饰器 3 行代码注册新工具，自动生成 JSON Schema |
| **作业场景适配** | ❌ 所有问题用同一套 prompt | ✅ 4 种预置场景（📐 数学 / 💻 编程 / 📝 写作 / 🔍 资料检索），点按钮一键切换 System Prompt |
| **中间推理过程** | ❌ 黑盒，一次性返回 | ✅ UI 以**可折叠的 Step 卡片**展示每一次工具调用的入参/结果 |
| **模型绑定** | ❌ 绑死自家模型 | ✅ LLM 抽象层，支持 OpenAI / DashScope / DeepSeek / 豆包，一行配置切换 |
| **Key 安全** | ❌ Key 在云端 | ✅ 本地 `.env`，全部流量可审计 |
| **离线可用** | ❌ 必须联网 | ✅ 内置 `MockLLM`，**0 成本跑通流程**，CI 友好 |

### 具体例子：`(12+8)*5 等于多少`

**普通 AI Chat**：直接文本生成 "100"（但实际上大模型经常在复杂算式上算错，因为它是"语言模型"而非"计算器"）。

**Course Agent**：
```
Step 1 🔧 调用工具 calculator
    参数: {"expression": "(12+8)*5"}
    结果: (12+8)*5 = 100
Step 2 ✍️ LLM 基于工具返回组织最终答案
最终答案: (12+8)×5 = 20×5 = 100，答案是 **100**。
```
**工具返回的是确定性结果，不存在幻觉**；UI 会把这两步都展示给你，过程完全透明。

---

## 🧠 架构速览

```
                    ┌────────────────────────────────────┐
  用户（学生）──→  │      Chainlit Web UI / CLI         │
                    └────────────────┬───────────────────┘
                                     │ on_message / chat
                                     ▼
                    ┌────────────────────────────────────┐
                    │      AgentLoop (ReAct 核心)        │
                    │                                     │
                    │   思考 → LLM.chat(tools=...)        │
                    │      │                              │
                    │      ▼                              │
                    │   有 tool_calls?  ─Y─→ 执行工具 ─┐  │
                    │      │ N                         │  │
                    │      ▼                    回写 tool msg
                    │   最终答案 ✅              │     │
                    └──────┬───────────────────────┬────┘
                           │                       │
                           ▼                       ▼
                    ┌────────────┐         ┌──────────────┐
                    │ LLM 抽象层 │         │ Tool Registry│
                    │            │         │              │
                    │ MockLLM    │         │ calculator   │
                    │ OpenAILLM  │         │ file_read    │
                    │ (任何 OpenAI│         │ file_write   │
                    │  兼容端点) │         │ web_search   │
                    └────────────┘         │ web_fetch    │
                                           │ recall       │
                                           │ remember     │
                                           │ + 你自定义的 │
                                           └──────────────┘
```

**关键抽象**：
- **AgentLoop**（[course_agent/core/agent_loop.py](course_agent/core/agent_loop.py)）同时暴露同步 `run()` 与异步 `arun()`，UI 层通过可选的 `AgentCallbacks` 订阅 `on_thought / on_tool_call / on_tool_result / on_final`。
- **BaseLLM**（[course_agent/llm/base.py](course_agent/llm/base.py)）屏蔽不同 Provider，新增 Provider 只要实现 `chat/achat`。
- **@tool 装饰器**（[course_agent/tools/registry.py](course_agent/tools/registry.py)）自动从函数签名 + docstring 生成 OpenAI Function-Calling 所需的 JSON Schema。

---

## 🕸️ LangGraph 图式运行时（Task 014）

从 Task 014 起，系统支持 **双运行时架构**：
- **`legacy`**：原有手写 Orchestrator 运行时
- **`langgraph`**：基于 LangGraph 的图式运行时（默认）

### 运行时切换

方式 1：临时切换 CLI / UI：
```bash
# 查看当前配置
uv run course-agent runtime

# 临时切换到 langgraph
uv run course-agent runtime --backend langgraph

# 导出图结构
uv run course-agent graph
```

方式 2：永久配置（`config/default.yaml`）：
```yaml
runtime:
  backend: langgraph    # legacy | langgraph
  checkpoint: memory
  draw_graph: true
```

方式 3：环境变量（优先级最高）
```bash
RUNTIME_BACKEND=langgraph uv run course-agent ui
```

### 为什么 LangGraph？
- **图式编排**：复杂流程（Plan→Solve→Critique→Refine→...）变为可描述、可视化的状态图；
- **Checkpointing**：支持状态保存与恢复；
- **Human-in-the-loop**：预留人工介入节点；
- **Parallel 预留**：为并行子任务执行保留扩展位；
- **Trace 全链路可观察**：完整图式执行全记录；
- **可视化**：graph 导出为 Mermaid 图；
- **生态兼容**：与 LangChain 工具链、LangSmith 追踪平台。

---

## 🔗 LangChain Adapter Layer

Task 014 没有为了接入 LangGraph 而推翻原有抽象，而是先补了一层 **LangChain 兼容适配层**：

- `LLMMessage` <-> LangChain `HumanMessage` / `AIMessage` / `ToolMessage` / `SystemMessage`
- `BaseLLM` -> `LangChainChatModelAdapter`
- `ToolRegistry` -> LangChain `StructuredTool`
- `CapabilityRegistry` -> LangChain Tool 视图

这样做的好处是：

- **保留稳定接口**：Task 008~013 已验证过的 `BaseLLM`、Tool、Capability 不需要整体重写；
- **让 LangGraph 可渐进接入**：先迁 runtime，再逐步迁更深层的 AgentLoop / memory / tracing；
- **方便后续生态扩展**：后面接 LangChain Runnable、LangSmith tracing 时，不必再重做一遍消息和工具桥接。

---

## ✅ 当前进度

| 里程碑 | 状态 | 内容 |
|---|---|---|
| Milestone 1 · MVP 骨架 | ✅ | Agent Loop、工具系统、CLI、配置、MockLLM |
| Task 003 · 接入真实 LLM | ✅ | OpenAI SDK + AsyncOpenAI + 限流重试 + 错误分类 |
| Task 004 · 浏览器 Web UI | ✅ | Chainlit + Step 可视化 + 多轮 + 场景按钮 + Settings 面板 |
| Task 007 · 记忆系统 + 真实检索 | ✅ | 短期滑动窗口 + LLM 摘要压缩；长期 Chroma 向量库；recall/remember 工具；Tavily/DuckDuckGo + trafilatura 真实联网 |
| **Task 008 · 让 Agent 真正动手做作业** | ✅ | **`python_exec` 沙箱（4 道安全闸）+ `pdf_read` PDF 阅读 + 错误分类细化（6 类）+ `course-agent doctor` 启动自检** |
| **Task 009 · 让 Agent「看见」+「自己批改」** | ✅ | **`image_ocr` 多模态视觉（Qwen-VL/GPT-4V）+ `code_solve` 自批改闭环（写→跑→改最多 3 轮）+ `python_exec` 白名单装包（numpy/pandas/scipy/...）+ `pdf_read` 扫描件 OCR 兜底 + Chainlit 拖拽图片上传 + doctor 第 8 项 VL 连通性** |
| **Task 010 · 让 Agent「记得住错」+「翻得到书」** | ✅ | **错题本（SQLite + SM-2 间隔复习）+ 教材 RAG（kb_ingest / kb_search 复用 Chroma 独立 collection）+ Chainlit 主动学习提示 + `/mistakes` 命令 + CLI `course-agent mistakes` 子命令 + doctor 第 9 项错题本+教材库** |
| **Task 011 · 让 Agent「答得顺」+「考得出」** | ✅ | **真流式输出（`StreamChunk` + `BaseLLM.astream()` + `AgentLoop.astream_run()` + Chainlit 打字机）+ 题目生成器 `generate_question`（基于错题本+教材 RAG，结构化 JSON）+ Examiner Agent（限定工具集 + 极简自动 grader，多 Agent 编排第一块砖）+ doctor 第 10 项流式+Examiner 探活** |
| **Task 012 · 让 Agent「分工合作」+「看得见账」** | ✅ | **多 Agent 编排（Planner / Solver / Critic / Orchestrator 四角分工，Plan→Solve→Critique→Refine 闭环，硬上限 30 LLM 调用）+ 可观测面板（SQLite metrics + `track_llm_call` + `course-agent metrics` 表格）+ Chainlit 数据层持久化（SQLAlchemy + aiosqlite，关闭浏览器历史不丢）+ Examiner 判分委托给 CriticAgent + doctor 第 11 项多 Agent 探活** |
| **Task 013 · 让 Agent「会借外脑」** | ✅ | **统一 Capability Layer（`internal_tool / skill / mcp`）+ Local Skill Runtime（`study_plan_skill` / `quiz_from_notes_skill`）+ MCP Adapter（mock-first，可选开启）+ Capability Router + capability metrics + CLI `capabilities/skills list/mcp list` + doctor 第 12 项 Skill/MCP 探活 + Chainlit Step 显示 `Tool / Skill / MCP` 来源** |
| **Task 014 · 让 Agent「运行在图上」** | ✅ | **LangGraph 图式运行时（双运行时架构 legacy/langgraph，可配置切换）+ LangChain Adapter Layer + `RuntimeConfig` + CLI `runtime/graph` 命令 + doctor 第 13 项 LangGraph 探活 + metrics 增加 `runtime_backend` 维度 + 默认 runtime 配置为 langgraph + Mermaid 图导出 + 新增 50 个测试用例** |
| Milestone 3 · 多 Agent 编排 | ✅ | Planner / Solver / Critic / Orchestrator 四角分工 + Refine 闭环（Task 012）|

---

## 🐍 Python 版本要求

**推荐：Python 3.13**（本项目锁定 `.python-version = 3.13`）。

| Python 版本 | 状态 | 说明 |
|---|---|---|
| **3.13** | ✅ 推荐 | Chainlit 官方支持，所有功能验证通过 |
| **3.12** | ✅ 支持 | 兼容 |
| **3.11** | ✅ 支持 | 兼容（`pyproject.toml` 最低版本） |
| **3.14** | ❌ **不支持** | Chainlit / anyio / starlette 对 3.14 适配不完整，会导致 Web UI 一片空白（静态资源返回 `anyio.NoEventLoopError`）|
| ≤ 3.10 | ❌ 不支持 | 使用了 3.11+ 的 `X \| Y` 类型语法 |

### 如果你本机没有 Python 3.13 / 用了不兼容版本，怎么办？

我们推荐使用 [`uv`](https://github.com/astral-sh/uv) 自动管理 Python 版本（不会污染你系统已有的 Python）：

#### 方案 A：让 uv 自动下载 3.13（**最省事，推荐**）

```bash
# 1. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 一条命令搞定——uv 读到项目里的 .python-version=3.13，
#    会自动下载并隔离一个 3.13 环境，完全不影响系统 Python
uv sync --extra dev

# 完成！现在所有 uv run ... 命令都会在 3.13 下运行
uv run course-agent ui
```

> 💡 `uv python install 3.13` 也可以手动预装；安装的是 CPython 官方发布包，解压到 `~/.local/share/uv/python/` 下，不写入 `/usr/local`、不改 `PATH`、**不会和你系统 Python 冲突**。

#### 方案 B：使用 pyenv

```bash
brew install pyenv                      # macOS
pyenv install 3.13.1
pyenv local 3.13.1                      # 在项目目录下固定

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
course-agent ui
```

#### 方案 C：使用 conda / miniforge

```bash
conda create -n course-agent python=3.13 -y
conda activate course-agent
pip install -e ".[dev]"
course-agent ui
```

#### 方案 D：必须用系统 3.14 的话（降级体验）

`course-agent chat ...`（CLI 模式）在 3.14 下**能跑**，因为走的是同步 `httpx`，不触发 starlette 静态文件问题；但 **Web UI 会一片空白**，这是 Chainlit 上游兼容问题，需要等 Chainlit/anyio 更新。如果确实无法升级环境，请暂时只用 CLI 模式。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 如果你还没有 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步依赖（首次会自动下载 Python 3.13）
uv sync --extra dev
```

### 2. 配置 API Key

复制模板：
```bash
cp .env.example .env
```

编辑 `.env`，填入你选用的 OpenAI 兼容 Provider 的 Key：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
```

支持的 Provider（把 `OPENAI_BASE_URL` 换成下面任意一个即可）：

| Provider | base_url | 可选 model |
|---|---|---|
| 阿里云百炼 (DashScope) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` / `qwen-turbo` / `qwen-max` / `qwen-long` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` / `deepseek-reasoner` |
| 火山豆包 (Ark) | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` 等 |
| OpenAI 官方 | *（留空使用默认）* | `gpt-4o-mini` / `gpt-4o` 等 |
| 🧪 离线 Mock | — | 把 `LLM_PROVIDER` 改为 `mock` 即可，无需 Key |

### 3. 启动方式

#### 🌐 方式 A：浏览器 Web UI（**推荐**）

```bash
uv run course-agent ui
```

然后浏览器打开 **http://localhost:8000**。你会看到：

- 🎨 类 ChatGPT 的现代聊天界面，支持 Markdown / LaTeX (`$...$`) / 代码高亮
- ⚡ **真流式输出（Task 011）**：token 级打字机效果，OpenAI `stream=True` → `StreamChunk` → `cl.Message.stream_token`，失败自动降级到非流式 `arun()`
- 🔧 **工具调用以可折叠 Step 卡片展示**——每一步 Agent 干了什么都清清楚楚
- 💬 多轮对话（会话级保留最近 10 轮）
- 🎯 **作业场景快捷按钮**：📐 数学 / 💻 编程 / 📝 写作 / 🔍 资料检索 / **📝 出题模式（Task 011）**，一键切换专属 System Prompt 或切换到 `ExaminerAgent`
- ⚙️ **Settings 面板**（右上角齿轮）：实时调整 `model` / `temperature` / `max_steps`
- 🌗 深色 / 浅色主题

自定义端口 / 对外开放：
```bash
uv run course-agent ui --port 9000
uv run course-agent ui --host 0.0.0.0 --port 8000
```

#### 💻 方式 B：CLI 单轮对话

```bash
# 真实 LLM，显示完整执行 trace
uv run course-agent chat "帮我算一下 (12+8)*5 等于多少" --trace

# 知识问答
uv run course-agent chat "用一句话总结牛顿第二定律"

# 查看已注册的工具
uv run course-agent tools

# 查看版本
uv run course-agent version
```

#### 🧪 方式 C：离线 Mock 模式（零成本验证）

把 `.env` 里的 `LLM_PROVIDER` 改为 `mock`（或删掉 `.env`），再：

```bash
uv run course-agent chat "帮我算一下 (3+5)*2 是多少"
```

Mock 模式下 Agent 依然会正确调用 `calculator` 工具，完整跑通 ReAct 流程，**不消耗 token**，适合写单元测试或本地开发。

---

## 🎬 使用场景示例

### 场景 1：数学作业

**用户**：帮我算 `((15+7)*3 - 9) / 2` 的结果，并说明计算步骤。

Agent 会自动：
1. 识别为数学问题 → 调用 `calculator` 工具
2. 工具返回 `((15+7)*3 - 9) / 2 = 28.5`
3. LLM 基于结果给出分步骤解释 + 最终答案

### 场景 2：编程作业（点击 💻 编程作业 按钮后）

**用户**：帮我写一个二分查找的 Python 程序。

Agent 会按「思路 → 代码 → 注释 → 测试用例」结构输出，代码放在高亮代码块里。

### 场景 3：文件批改

**用户**：读取 `~/Desktop/homework.py` 并找出其中的 bug。

Agent 会：
1. 调用 `file_read` 读取文件
2. LLM 分析代码
3. 返回 bug 定位 + 修复建议（可选：调用 `file_write` 写入修复版本）

### 场景 4：自己写新工具

只需在 [course_agent/tools/builtin.py](course_agent/tools/builtin.py) 旁边新增一个函数：

```python
from course_agent.tools.registry import tool

@tool(name="latex_render", description="把 LaTeX 片段渲染成说明文字")
def latex_render(code: str) -> str:
    ...
```

Agent 重启后就会自动发现这个工具并在合适时机调用它——**不改 prompt、不改 Loop，一行装饰器搞定**。这是 Agent 架构相比普通 Chat 最大的扩展点优势。

---

## 🧠 记忆系统（Task 007）

### 为什么需要它？

普通 LLM 调用是「无状态」的——同一个会话内靠 history 撑着，换一个浏览器标签页、明天再回来，AI 就完全不记得你是谁、上次聊到哪。Course Agent 在 Task 007 引入了**双层记忆**：

| 层 | 实现 | 生命周期 | 解决的问题 |
|---|---|---|---|
| **短期记忆 ShortTermMemory** | 滑动窗口（默认 20 轮）+ **超过 16 轮自动用 LLM 把最旧那一半压缩成 ≤200 字摘要** | 单会话 | 长对话不爆 token、保留早期上下文要点 |
| **长期记忆 LongTermMemory** | **Chroma `PersistentClient`**（cosine HNSW）+ Embedder | **跨会话持久化**（落盘到 `data/memory/<session_id>/`） | 关掉浏览器明天回来，AI 还记得"我喜欢用 Python" |

### 工作流程

每一轮 `on_message` 实际经过 [`MemoryManager.enrich_context()`](course_agent/memory/manager.py)：

```
用户输入 ──┐
            ├──→ ① 用 user_input 去 long.recall(k=3) 检索语义最相关的历史片段
            │       ──→ 注入一条 system message: [RELEVANT MEMORIES] ...
            │
            ├──→ ② short.compressed_history()
            │       ──→ 拼上 [SUMMARY] xxx + 最近 N 轮原始消息
            │
            └──→ ③ 拼成最终 history 喂给 AgentLoop
                    └──→ 回答完后 add_user / add_assistant 同步写入两层
```

### Embedder 自动选择

[`embedders.create_embedder()`](course_agent/memory/embedders.py) 会按以下优先级挑：

1. 设置了 `OPENAI_API_KEY` → **OpenAIEmbedder**（DashScope `text-embedding-v3` 或 OpenAI `text-embedding-3-small`，1024 维真实语义向量）
2. 否则 → **HashEmbedder**（MD5+L2 归一化的 256 维 hash 向量，**完全离线、零依赖**，单测和 CI 默认走它）

→ 这意味着**没有 Key 也能跑通整个记忆链路**，是 CI 友好的核心设计。

### Agent 可调用的两个新工具

| 工具 | 签名 | 干嘛 |
|---|---|---|
| `recall(query, k=3)` | 语义检索长期记忆 | LLM 觉得"我应该回忆一下用户之前说过什么"时主动调用 |
| `remember(content, tag="note")` | 主动把一条信息写入长期记忆 | 用户说"记住我喜欢 Python"时，LLM 调用此工具固化 |

### 在 Web UI 里使用

打开右上角 ⚙️ Settings 面板，你会看到一个 **Switch: 启用长期记忆**：
- 开（默认）：每会话独立 `data/memory/<session_id>/`，关闭浏览器后再回来，新会话依然能 `recall` 历史
- 关：只保留单会话短期记忆，重启就忘

切换 📐 数学 / 💻 编程 等场景按钮时，**只清空短期记忆，保留长期记忆**——这样切换学科不会丢失你的偏好。

### 实测：跨会话回忆

```
会话 1：「请记住我的名字是小明，我最喜欢用 Python」
        → LLM 调用 remember(content="小明喜欢 Python")
        → Chroma 落盘到 data/memory/<sid_1>/

[关闭浏览器，明天再开]

会话 2（同一持久化目录）：「我之前告诉过你我叫什么吗？」
        → enrich_context 自动 recall → 注入 [RELEVANT MEMORIES]
        → LLM 回答：「你叫小明，喜欢 Python」 ✅（实测 score=0.52）
```

---

## 🌐 真实 Web 检索（Task 007）

旧版 `web_search` 只是返回固定字符串 mock。Task 007 接入了真实搜索：

| Provider | 触发条件 | 说明 |
|---|---|---|
| **Tavily** | 设置了 `TAVILY_API_KEY` | 优先使用，质量最高，免费额度足够个人用 |
| **DuckDuckGo** | 任何时候（保底） | 通过 [`ddgs`](https://github.com/deedy5/ddgs) 库无需 Key，完全免费 |

外加一个 [`web_fetch(url, max_chars)`](course_agent/tools/web_tools.py) 工具：用 `httpx` 拉网页 → `trafilatura` 抽正文 → 失败回退到 HTML 标签剥离。这样 Agent 可以**先 search 拿 URL，再 fetch 拿正文**，组成完整的"搜+读"闭环。

### 配置（可选）

```env
# 不配也能用 DuckDuckGo 兜底
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
```

### 试一下

```bash
uv run course-agent ui
# 在界面里问："帮我搜一下 Python 3.13 有哪些新特性，并把第一个结果的正文抽出来"
# Agent 会自动 web_search → web_fetch 两步
```

---

## 🔬 沙箱执行 `python_exec`（Task 008）

让 Agent 写完 Python 代码后**真的跑一下**，把 `stdout / stderr / exit_code` 拿回来再回答你——不再靠 LLM「目测」结果。

```bash
# 在 UI 或 CLI 里直接对话
uv run course-agent chat "写一个二分查找，并验证在 [3,5,7,11,13] 中找 7 的位置"
# Agent 会：① 写代码 → ② 调用 python_exec 跑 → ③ 把真实 stdout 给你
```

**四道安全闸**（详见 [task_008.md §4.1](task/task_008.md)）：

| 闸 | 防什么 | 怎么做 |
|---|---|---|
| ① AST 静态校验 | 恶意 import / `os.system` | 黑名单：`subprocess` / `socket` / `ctypes` / `shutil` / `multiprocessing` / `os.system|popen|exec*|fork` |
| ② 隔离子进程 | 污染父进程 / 偷读 secret | 临时 cwd + `python -I -S` 隔离模式 + 净化 env（剥离 `OPENAI_*` / `AWS_*` / `*_proxy`） |
| ③ 资源限制 | 死循环 / 内存炸 / fd 泄漏 | Linux/macOS：`RLIMIT_CPU=5s` + `RLIMIT_AS=256MB` + `RLIMIT_NOFILE=64` |
| ④ 输出截断 | 巨量打印冲爆上下文 | stdout ≤ 8KB，stderr ≤ 4KB，超时 5s 强制 kill |

⚠️ **半信任模型**：足够防住学生作业意外死循环 / 误删本地文件，但**不能**抵御主动攻击。生产环境部署请加 Docker / gVisor 强隔离。

返回结构化 JSON：
```json
{"exit_code": 0, "stdout": "...", "stderr": "", "duration_ms": 87, "truncated": false, "timed_out": false}
```

---

## 📄 PDF 阅读 `pdf_read`（Task 008）

学生作业题目 90% 是 PDF。`file_read` 读 PDF 会出乱码——`pdf_read` 用 [`pypdf`](https://pypdf.readthedocs.io/) 抽纯文本：

```bash
# 直接对话
uv run course-agent chat "请读一下 ~/Downloads/homework.pdf 第 1-3 页，告诉我题目要求"
```

支持参数：
- `path` — 本地 PDF 路径
- `page_range` — `"1-3"` / `"1,3,5"` / `"2-"` / `"-3"` / `""`（默认全部）
- `max_chars` — 累计字符上限，默认 8000，硬上限 65536

**扫描件 OCR 兜底**（Task 009）：当抽出文本极少（最大单页 < 10 字符）时，会自动尝试用 `pypdfium2` 把第一页渲染成 PNG 并调 `image_ocr` 抽文字（前提：装了 `pypdfium2` + 在 `.env` 配置了 `VL_MODEL`）。否则给出明确的「兜底 OCR 未启用」提示，**绝不返回空字符串**。

返回示例：
```
[pdf_read] 文件：homework.pdf ｜ 共 5 页 ｜ 本次返回页：1,2,3 ｜ 截断：否

[Page 1]
本次作业：实现冒泡排序，并分析最坏时间复杂度。
......
```

---

## 🩺 启动自检 `course-agent doctor`（Task 008）

Task 007 那次 `[LLM 认证失败]` 事故的产物——**不要等到第一次发消息才发现 Key 配错了**。

```bash
uv run course-agent doctor
```

7 项检查（Task 009 起新增第 8 项「VL 多模态连通性」；Task 010 第 9 项「错题本+教材库」；**Task 011 第 10 项「流式 + Examiner Agent」**；**Task 012 第 11 项「多 Agent + Orchestrator」**；**Task 013 第 12 项「Skill + MCP 能力层」**，共 12 项）：

| # | 项目 | 检查内容 |
|---|---|---|
| 1 | Python 版本 | 锁定 3.11~3.13；3.14 警告（chainlit/anyio 不兼容） |
| 2 | 关键依赖 | `openai` / `chainlit` / `chromadb` / `pypdf` / `trafilatura` ... 10 个包 |
| 3 | `.env` 文件 | 是否存在 + 大小 |
| 4 | OPENAI_API_KEY | 显示尾号 6 位 + 长度；同时检测 shell OS env 是否残留旧 key |
| 5 | LLM chat | 真实发一次 `ping`，记录 200/失败 + 时延 |
| 6 | LLM embedding | 真实调一次 embed，记录 dim + 时延（失败 ⚠️ 自动降级 HashEmbedder，不算错） |
| 7 | **VL 多模态连通性**（Task 009） | 配了 `VL_MODEL` 时用 1×1 PNG 真实探活；未配则 ⚠️ 跳过并提示「`image_ocr` 与 `pdf_read` 扫描兜底将自动降级」 |
| 8 | 工具注册 | 17 个工具是否全部就位 |
| 9 | 错题本 + 教材库 | SQLite mistakes.db 可读写 + Chroma kb_textbook chunk 数 |
| 10 | **流式 + Examiner Agent**（Task 011） | `llm.astream()` 1 个 chunk 真实探活 + `ExaminerAgent` 限定工具集可实例化；mock/无 key 时跳过为 ⚠️ 但仍验证 Examiner |
| 11 | **多 Agent + Orchestrator**（Task 012） | 4 个 Agent（Planner / Solver / Critic / Orchestrator）可实例化 + metrics.db 就绪；真 LLM 跑一个 `max_sub_tasks=1 / max_refine=0` 的最小 hello roundtrip；mock / 无 key 时跳过为 ⚠️ 但仍验证实例化 |
| 12 | **Skill + MCP 能力层**（Task 013） | Capability Registry 可实例化；至少能发现内部工具 + Local Skill；MCP 未开启时 ⚠️ skip，不算失败；开启 mock provider 后可枚举 MCP 能力 |

任何 `❌` 都会让 doctor 退出码非 0，方便 CI / 容器健康检查接入。

---

## 🖼️ 图片识别 `image_ocr`（Task 009）

让 Agent 能「看见」——把学生拍的题目截图、黑板板书、手写公式、扫描件截图喂给多模态 LLM（Qwen-VL / GPT-4V / Claude Vision）抽出纯文本。

```bash
# 1. 在 .env 配置（可选；不配时工具会友好降级，不抛错）
VL_MODEL=qwen-vl-plus
VL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VL_API_KEY=sk-xxx     # 不填则自动复用 OPENAI_API_KEY

# 2. CLI 体验
uv run course-agent chat "请用 image_ocr 识别 ~/Pictures/board.jpg 然后帮我解题"

# 3. Web UI 直接拖图（推荐）
uv run course-agent ui
# 在对话框拖入 1~3 张图（≤10 MB / 张），Agent 会自动调 image_ocr
```

**实现要点**：
- 路径 / URL **自动判别**：URL 用 `httpx` 下载到内存；本地路径直接读
- 字节 → base64 → `data:image/...;base64,` data URL（OpenAI 多模态消息格式）
- `temperature=0.0` 确定性输出；`max_tokens=2048`
- 图片大小 ≤ 10 MB；输出截断 ≤ 16 KB
- **未配置 VL_MODEL / 调用失败 / 返回空** 三种情况都返回友好的 `[image_ocr] ...` 提示，**绝不抛异常**

---

## 🔁 自批改闭环 `code_solve`（Task 009）

Task 008 让 Agent 能「跑代码」，Task 009 让 Agent 能「写错了**自己改**」——把「写 → 跑 → 失败 → 改 → 再跑」这个循环显式编排出来，最多 N 轮，**有硬上限不会死循环**。

```bash
# 在 UI / CLI 里这样问：
uv run course-agent chat "用 code_solve 写一个判断回文数的函数 is_palindrome(n)，
用 assert is_palindrome(121) == True 和 assert is_palindrome(123) == False 验证"

# Agent 会：
#   ① LLM 写代码 → ② python_exec 跑（含自动追加的断言）
#   ③ exit_code == 0 → 通过 ✅
#      exit_code != 0 → 把 stderr 截前 1KB 喂回 LLM，让它**只返回完整修正后的代码**
#   ④ 重复 ②③ 最多 max_rounds 轮（默认 3，硬上限 5）
```

**返回结构化 JSON**：
```json
{
  "success": true,
  "rounds": 2,                 // 实际花了几轮
  "code": "def is_palindrome(n):\n    ...\n# === auto tests ===\nassert ...",
  "last_error": "",
  "attempts": [
    {"round": 1, "code": "...", "exit_code": 1, "stderr": "AssertionError ..."},
    {"round": 2, "code": "...", "exit_code": 0, "stderr": ""}
  ]
}
```

**失败诚实返回**：故意给一个无解需求（"写一个永远返回 True 的函数让 `assert f(0) == False`"），3 轮后会返回 `success=False` + `已尝试 3 轮仍未通过`，**不会无限烧 token**。

**实现要点**：
- 工具内部通过 `course_agent.llm.factory.get_default_llm()` 拿 LLM 单例
- 第 1 轮 / 重试轮用**不同的 system prompt**：第 1 轮要求只用标准库；重试轮明确「只返回修正后完整代码，不要解释、不要道歉」
- 用正则 ```` ```python ... ``` ```` 抽代码块，找不到就把整段当代码兜底
- 喂回 LLM 的 stderr 截断 1KB，避免上下文越滚越长

---

## 📦 沙箱白名单装包 `python_exec(extra_packages=...)`（Task 009）

Task 008 的沙箱默认 `python -I -S` 完全隔离，**连 `numpy` 都 import 不到**——对纯 stdlib 的算法题够用，但数据科学 / 数学题就抓瞎了。Task 009 给 `python_exec` 加了一个**受控的白名单装包**机制：

```python
# Agent 可以这样调（白名单内的包按需 pip install --target 到本地缓存）
python_exec(
    code="import numpy as np\nprint(np.zeros(3).sum())",
    extra_packages=["numpy"],   # 仅允许白名单内的包
)
```

**白名单**（6 个）：`numpy / pandas / matplotlib / scipy / sympy / requests` —— 覆盖 90% 的数据科学 / 数学 / 简单网络题目。

**安全设计**：
- ❌ 任意包名（如 `pyyaml` / `evil-pkg`）会被**直接拒绝**，返回 `[error] ... 不在白名单`
- 装包目录：`~/.cache/course-agent/pkgs/shared/`（**跨调用复用**，第 2 次起秒级）
- 已在缓存里的包跳过 `pip install`；缺的才装；超过 120s 超时报错
- 装完通过 `PYTHONPATH` 注入子进程；同时把 `python -I -S` 降级为 `python -S`（`-I` 会忽略 `PYTHONPATH`，必须降级），但 AST 黑名单 / 净化 env / rlimit / 超时 / 输出截断**全部保留**
- ✅ **完全向后兼容**：不传 `extra_packages` 时行为与 Task 008 100% 一致

---

## 📓 错题本（Task 010）

Memory 系统是「相似度检索」，但**陪学的核心是错题分类账**——学生错过什么 / 多久没复习 / 今天该过什么——这些都需要结构化的状态而不是向量回忆。Task 010 用 **SQLite + SM-2 间隔复习算法**实现了一个轻量的「错题账本」。

**3 个工具**（Agent 可以自动调用）：

```python
# 1) 记入一道错题
add_mistake(
    question="什么是 RSA 加密？",
    correct_answer="基于大整数分解困难的非对称加密",
    tags="密码学,RSA",
    source="textbook P.42",
)
# → ✅ 已记入错题本（#1）。

# 2) 查询错题
list_mistakes(tag="密码学")          # 按标签过滤
list_mistakes(due_only=True)         # 仅今日待复习
list_mistakes(limit=20)              # 默认 20 条

# 3) 复习打分（0-5 → SM-2 算法更新下次复习日期）
review_mistake(mistake_id=1, quality=5)
# 0=完全不会 / 1=想起来但错 / 2=错但有印象 / 3=磕巴对 / 4=流畅对 / 5=秒答
# quality<3 → 间隔重置为 1 天；quality≥3 → 1 天 → 6 天 → 6×EF 天 → ...
```

**CLI 子命令**（不进 Chainlit 也能管错题）：

```bash
uv run course-agent mistakes list                # 列全部
uv run course-agent mistakes list --tag 线代     # 按标签过滤
uv run course-agent mistakes due                 # 今日待复习
uv run course-agent mistakes review 3 5          # 对 #3 打 5 分
```

**Chainlit 集成**：
- 启动时若有今日待复习错题，欢迎语后**自动追加** `📓 今天有 N 道错题待复习` 提示
- 输入 `/mistakes` 直接列表（不走 LLM，秒回）

**存储**：`~/.cache/course-agent/mistakes.db`（与 `python_exec` 包缓存同根，`course-agent doctor` 第 9 项一并检查）。

---

## 📚 教材 RAG `kb_ingest` + `kb_search`（Task 010）

把整本教材一次性塞进 context 既贵又会爆——但学生提问时确实需要 Agent **能翻到原文**。Task 010 做了一个**轻量的本地教材 RAG**：

```python
# 1) 摄入一份教材（PDF / Markdown / TXT）
kb_ingest("data/textbook/discrete_math.pdf")
# → ✅ 已摄入 312 个 chunk，来源：discrete_math.pdf（共 280 页）。
#   PDF 自动按页切，并把页码写入 metadata；扫描件 PDF 走 Task 009 的 image_ocr 兜底。

# 2) 检索带页码的相关段落
kb_search("RSA 加密原理", top_k=3)
# → 📚 教材库检索：query='RSA 加密原理'，命中 3 段
#    --- [📚 discrete_math.pdf P.42] ---
#    RSA 是一种基于大整数分解困难性的非对称加密……
#    --- [📚 discrete_math.pdf P.43] ---
#    ...
```

**设计要点**：
- **独立 Chroma collection** `kb_textbook`，与 Memory 的 `long_term` 完全隔离
- **持久化路径** `data/kb/`，与 Memory 的 `data/memory/<session>` 互不污染
- **Chunk 策略**：固定 800 字符 + 100 字符 overlap，中文友好且零依赖
- **稳定 ID**：`source::pX::cN::hash[:8]`，二次 ingest 同一份教材会**覆盖**而非重复入库
- **HashEmbedder 兜底**：没配 `OPENAI_API_KEY` 也能用，但结果末尾会**显著提示** `⚠️ 当前用 hash 兜底，召回率有限`，绝不假装效果
- **支持扩展名**：`.pdf` / `.md` / `.markdown` / `.txt`

**Agent 引用规范**（推荐写进 system prompt）：

> 当你调用了 `kb_search` 并基于结果回答时，请在答案末尾附上「📚 参考：xxx P.42」便于学生回去翻书。

---

## ⌨️ 真流式输出（Task 011）

学生最直观的「卡顿感」往往不是 LLM 慢，而是「等了 8 秒才一次性蹦出整段答案」。Task 011 把整条链路改成 **token 级真流式**：

```
OpenAI SDK stream=True
        │
        ▼
BaseLLM.astream() ──→ AsyncIterator[StreamChunk]
                       (delta_text / tool_call_delta / finish_reason / error)
        │
        ▼
AgentLoop.astream_run() ──→ 逐 token 透出 + 跨 chunk 拼装 tool_call.arguments
        │
        ▼
Chainlit on_message: cl.Message.stream_token(token) ──→ 浏览器打字机效果
```

**关键设计**：

| 抽象 | 位置 | 干嘛 |
|---|---|---|
| `StreamChunk` | [llm/base.py](course_agent/llm/base.py) | 统一流式单元：`delta_text` / `tool_call_delta` / `finish_reason` / `error` |
| `BaseLLM.astream()` | [llm/base.py](course_agent/llm/base.py) | 抽象方法；**默认实现**调 `achat()` 后切成 4 字符假流（兜底，让 MockLLM 不改也能流） |
| `OpenAILLM.astream()` | [llm/openai_like.py](course_agent/llm/openai_like.py) | 真实 `stream=True`；逐 chunk yield；任何异常包成 `finish_reason="error"` |
| `AgentLoop.astream_run()` | [core/agent_loop.py](course_agent/core/agent_loop.py) | 异步生成器；遇 `tool_calls` 时跨 chunk 拼 `arguments` JSON 增量；执行工具后再续流 |
| Chainlit `on_message` | [ui/chainlit_app.py](course_agent/ui/chainlit_app.py) | `cl.Message.stream_token()`；流式失败 → 整体降级到 `arun()` 二次发送 |

**容错链**：

1. `OpenAILLM.astream()` 单 chunk 异常 → yield `StreamChunk(finish_reason="error", error=...)` 而不是抛
2. `AgentLoop.astream_run()` 收到 `error` 后 → `await self.arun()` 一次性出最终答案
3. Chainlit `on_message` 整段流式异常 → 再外一层 try → fallback 用 `arun()` 重新 send 一条新消息

任意一层失败都能优雅降级，**不会出现"半截白屏"或抛 traceback 给用户**。

**向后兼容**：`AgentLoop.run()` / `arun()` 完全不变，**默认 ReAct 仍按非流式跑**；流式只在 Chainlit `on_message` 中通过 `astream_run()` 显式开启。

---

## 📝 Examiner Agent 出题模式（Task 011）

**多 Agent 编排的第一块砖**：用「**限定工具集 + 独立 system_prompt**」的薄壳把 `AgentLoop` 改造成专职「出题人 + 极简自动 grader」。

### 怎么用

Chainlit 启动后，点欢迎区的「**📝 出题模式**」按钮：

```
你 → 进入出题模式
Examiner → 🔧 调用工具 generate_question(tag="线代,特征值")
         → ### 📝 新题（解答题 · 难度 中）
            求矩阵 A=[[2,1],[1,2]] 的特征值。
            📚 参考：线代教材 P.83  ｜  基于错题：（无）

你 → 我觉得 λ=2,4
Examiner → ❌ 答错，正确答案是 λ1=3, λ2=1（解 det(A-λI)=0 即可）
         → 🔧 调用工具 add_mistake(question="...", correct_answer="...", tags="线代,特征值", source="examiner_generated")
         → ✅ 已记入错题本（#7）
         → 要再来一道同类型的题吗？
```

### 三道关键栅栏

| 栅栏 | 实现 | 防什么 |
|---|---|---|
| **限定工具集** | [`agent/examiner.py`](course_agent/agent/examiner.py) 的 `_EXAMINER_ALLOWED_TOOLS = ("generate_question", "kb_search", "add_mistake", "list_mistakes", "review_mistake")` | LLM 走神调 `python_exec` / `web_search` 等无关工具 → 直接从 `tool_names` 白名单里抹掉，schema 里都没有 |
| **独立 system_prompt** | `EXAMINER_SYSTEM_PROMPT` 强制 0-5 评分规则 + `quality<3` 自动调 `add_mistake` | 没 prompt 引导，LLM 不会「答错→入错题本」这种闭环 |
| **复用 AgentLoop** | `ExaminerAgent` 内部组合一个 `AgentLoop`，**不重复实现循环** | 双份维护、行为漂移 |

### `generate_question` 工具

[`tools/generator.py`](course_agent/tools/generator.py) 的 `generate_question(tag, question_type, difficulty, n_refs)`：

1. `kb_search(tag)` 拿 `n_refs` 段教材作素材（HashEmbedder 兜底时显著标注 ⚠️）
2. `_query_past_mistakes(tag)` 拿同 tag 下学生答错过的题目作为 `avoid_repeat` 黑名单
3. 调 `get_default_llm().chat()` 出题，**强制 JSON 输出**（schema：`question / correct_answer / explanation / source / based_on_mistakes / type / difficulty`）
4. JSON 解析失败 → **自动重试 1 次**（附带"上次输出无法解析"的强提示）；两次都失败 → 友好提示 + 截断 200 字原始响应（**不抛异常**）
5. 返回 markdown：题面 + 教材出处 + 末尾的 ```` ```correct``` ```` 代码块（`correct_answer` 与 `explanation` 内嵌其中，仅供 Examiner 自批改读取，prompt 引导其不要直接展示给学生）

### 故意不让 generate_question 写错题本

工具单一职责：**写不写错题本由 Examiner 在判分后决定**，避免出题工具被普通 ReAct Agent 误用时把生成题也当作错题入库。

---

## 🧪 运行测试

```bash
# 默认只跑离线测试（不需要 Key，~2 秒）
uv run pytest

# 包含在线集成测试（真实调用 LLM，需要 Key）
RUN_LIVE_LLM=1 uv run pytest

# 包含真实 DuckDuckGo / web_fetch 联网测试
RUN_LIVE_WEB=1 uv run pytest tests/test_web_tools.py

# 代码风格检查
uv run ruff check .
```

**当前测试状态**：**357 passed + 6 skipped**（live tests 默认跳过；Task 014 在原有 307 个基线用例上新增 50 个回归测试，覆盖 runtime backend、LangGraph orchestrator、LangChain adapter、CLI runtime/doctor、metrics backend 和 Chainlit runtime 切换）。

---

## 🧩 多 Agent 编排（Plan / Solve / Critic / Orchestrator）（Task 012）

Task 011 的 `ExaminerAgent` 是**单 Agent 跑全场**——只是 prompt 和工具集变窄。Task 012 解决的是**真正的「分工合作」问题**：「帮我把这份作业全做完」不是一个 Agent 该一个人扛的活。

### 四角分工

| Agent | 工具白名单 | system_prompt 关键词 | 输出格式 |
|---|---|---|---|
| **Planner** | `kb_search` / `list_mistakes` | "拆 1～5 个有序、可独立执行的 sub-task" | JSON `{plan_summary, sub_tasks: [{id, title, expected_output, suggested_tools}]}` |
| **Solver** | **全工具集**（动手干活） | "直接给出满足 expected_output 的最终结果" | 自由 markdown |
| **Critic** | `kb_search`（仅核对教材） | "score 0-5，pass=score>=3" | JSON `{score, pass, feedback}` |
| **Orchestrator** | 无（自己不调 LLM） | — | `OrchestratorResult{final_answer, plan, sub_results, total_llm_calls}` |

### Plan → Solve → Critique → Refine 闭环

```
用户原始任务
    │
    ▼  （1 次 LLM）
Planner → JSON sub_tasks  ← JSON 解析失败重试 1 次；仍失败 → 单 sub_task 降级
    │
    ▼
for each sub_task:
    Solver.solve(sub_task) → answer        ── 1 次 LLM
        │
        ▼
    Critic.critique(sub_task, answer)      ── 1 次 LLM
        │
        ├── pass=True  → 进入下一个 sub_task
        └── pass=False → 把 Critic feedback 注入 history → 回 Solver 重跑
                          （最多 max_refine_per_task=2 轮）
    │
    ▼
合成 final_answer（多 sub_task 时按 "## 最终答案 / ### Sub-Task #n" 分段拼接）
```

### 三道硬上限（防 token 失控）

| 参数 | 默认 | 触发后行为 |
|---|---|---|
| `max_sub_tasks` | 5 | Planner 输出超过则截断 |
| `max_refine_per_task` | 2 | 每个 sub_task 最多 refine 2 轮（Solver 重跑 2 次）|
| `max_total_llm_calls` | 30 | **抛 RuntimeError**（防死循环）|

### 四道降级保护

1. **Planner JSON 解析失败**：重试 1 次 → 仍失败 → 单 sub_task 模式（把原任务整段丢给 Solver），无 traceback 暴露
2. **Critic JSON 解析失败**：重试 1 次 → 仍失败 → 保守通过（`{score: 3, pass: True, feedback: "⚠️ Critic JSON 解析失败，默认通过"}`），不阻塞主流程
3. **达 LLM 调用上限**：保留当前 sub_task 结果，跳过后续 Critic
4. **Refine 上限**：保留最后一次 Solver 输出（即使 critic 仍 fail），继续下一个 sub_task

### Chainlit 复杂任务模式

点欢迎区的「**🧩 复杂任务模式**」按钮 → 输入复杂任务 → UI 按 Agent 分层展示：

```
🧩 复杂任务模式：读完 ~/Desktop/hw.pdf 第 1-3 页提取题目 + 出 1 道相似新题
[Step] Plan        → 1) 抽取 hw.pdf 题目  2) 出 1 道相似新题
[Step] Sub-Task #1 → ✅ score=4/5 ｜ refine=0 轮 ｜ <Solver 输出截断 600 字>
[Step] Sub-Task #2 → ✅ score=5/5 ｜ refine=1 轮 ｜ <Solver 输出截断 600 字>
（主消息）## 最终答案 / ### Sub-Task #1：... / ### Sub-Task #2：...
```

### 代码结构

| 模块 | 职责 |
|---|---|
| [agent/base.py](course_agent/agent/base.py) | `BaseAgent` Protocol（`runtime_checkable`，鸭子类型契约）+ `AgentMessage` Pydantic 模型 |
| [agent/planner.py](course_agent/agent/planner.py) | `PlannerAgent.plan()` → list[sub_task]；JSON 解析 + 重试 + 单段降级 |
| [agent/solver.py](course_agent/agent/solver.py) | `SolverAgent.solve(sub_task, history)` → AgentResult；薄壳 ReAct |
| [agent/critic.py](course_agent/agent/critic.py) | `CriticAgent.critique(sub_task, answer)` → `{score, pass, feedback}` |
| [agent/orchestrator.py](course_agent/agent/orchestrator.py) | `Orchestrator.arun(user_task)` → `OrchestratorResult` |

### Examiner 判分委托

ExaminerAgent 新增可选 `critic` 构造参数 + `judge_answer()` 方法 —— 学生交卷时不再依赖 system_prompt 的「自我打分」，而是委托给独立 CriticAgent（避免单 Agent 自评偏差）。Critic 实例化失败时仍自动降级回原本的 system_prompt 自评，向后兼容。

---

## 📊 可观测面板（`course-agent metrics`）

多 Agent 编排会引入「token 都花到哪个角色了？哪个 Agent 出错率高？」的运维问题。Task 012 加了一个**轻量的 SQLite metrics 落库 + CLI 表格展示**。

### 数据表

`~/.cache/course-agent/metrics.db`（可用 `COURSE_AGENT_METRICS_DB` 环境变量覆写）：

```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    agent_name TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ok',
    error TEXT
);
```

### 自动落库的入口

`course_agent/llm/openai_like.py` 的 `chat()` / `achat()` / `astream()` 全部包了 `track_llm_call()` 上下文管理器，**自动**记录每次 LLM 调用：

```python
with track_llm_call(model=self.model) as rec:
    resp = client.chat.completions.create(...)
    rec.prompt_tokens = resp.usage.prompt_tokens
    rec.completion_tokens = resp.usage.completion_tokens
```

`agent_name` 通过 **contextvar** 传递（`set_current_agent("Planner")` 在每个 Agent 入口调用），异步安全跟着 task 走，不会窜场。

### 失败不阻塞

metrics 写入异常**只 log warning，不抛出**——可观测性是辅助，不能影响主流程。

### CLI 用法

```bash
# 看最近 50 次按 Agent 聚合的统计
uv run course-agent metrics

# 看最近 200 条 + 原始记录
uv run course-agent metrics --limit 200 --raw
```

输出示例：

```
📊 最近 50 次 LLM 调用按 Agent 聚合
┏━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
┃ Agent        ┃ 调用数 ┃ Tokens (in/out) ┃ 平均时延 ┃ 错误率 ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━┩
│ Solver       │     12 │       8420/3120 │   1830ms │   0.0% │
│ Critic       │      9 │        3240/280 │    980ms │   0.0% │
│ Planner      │      3 │         860/210 │   1120ms │   0.0% │
└──────────────┴────────┴─────────────────┴──────────┴────────┘
```

---

## 💾 会话持久化（Chainlit data layer）（Task 012）

Chainlit 默认每次刷新页面就忘光历史。Task 012 接入了 **Chainlit 官方 SQLAlchemy data layer**，把 message / step / thread 全部落到本地 SQLite：

```python
# course_agent/ui/chainlit_app.py（模块顶层）
import chainlit.data as cl_data
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

@cl_data.data_layer
def _get_data_layer():
    return SQLAlchemyDataLayer(
        conninfo=f"sqlite+aiosqlite:///{Path('data/chainlit.db').resolve()}"
    )
```

**注意**：`cl_data.data_layer` 装饰器**必须在模块顶层执行**（不能放到 `on_chat_start` 里），否则 Chainlit 启动时拉不到。失败时静默 log warning，UI 仍能跑，只是无持久化。

依赖：`sqlalchemy>=2.0` + `aiosqlite>=0.19`（已写入 [pyproject.toml](pyproject.toml)）。

---

## 🧰 统一 Capability Layer（Task 013）

Task 012 的 Agent 已经会「分工合作」，但能力来源仍然被仓库里的 `tools/` 锁死。Task 013 把“能力”进一步抽象成统一对象，让上层不再区分“这是内置工具、Skill，还是外部 MCP server 提供的能力”。

### 三类能力

| Kind | 含义 | 典型来源 |
|---|---|---|
| `internal_tool` | 现有 `ToolRegistry` 里的底层工具 | `calculator` / `pdf_read` / `kb_search` |
| `skill` | 本地高层能力封装，通常是“任务模板 + 参数 schema + 执行器” | `study_plan_skill` / `quiz_from_notes_skill` |
| `mcp` | 外部 MCP server 暴露的能力 | `mcp_demo_echo` / `mcp_demo_keyword_extract` |

### 统一抽象

- [capabilities/base.py](course_agent/capabilities/base.py)：`CapabilityKind` / `CapabilitySpec` / `CapabilityCallResult` / `BaseCapabilityProvider`
- [capabilities/registry.py](course_agent/capabilities/registry.py)：统一聚合 provider，按 `kind / enabled` 过滤
- [capabilities/router.py](course_agent/capabilities/router.py)：给不同 Agent 暴露不同能力集合
- [capabilities/adapters.py](course_agent/capabilities/adapters.py)：把 `ToolRegistry` 包成 provider，并把 capability 再包装回 AgentLoop 可消费的“工具视图”

### 为什么不直接推翻 ToolRegistry？

因为 Task 013 的目标是**渐进式引入**。现有 Tool 体系、AgentLoop、Task 012 的多 Agent 流程都保持可用；Solver 只是在需要时额外看到 Skill / MCP，不会破坏老链路。

---

## 🧠 Skill Runtime（Task 013）

Skill 不是更底层的工具，而是**更高层的能力封装**。它可以带自己的输入输出约定、参数 schema，甚至内部再组合多个工具。

### 本期内建的 2 个 Skill

| Skill | 作用 |
|---|---|
| `study_plan_skill` | 基于主题和天数生成结构化复习计划 |
| `quiz_from_notes_skill` | 基于一段笔记文本生成 1~5 道练习题 |

### 运行时结构

- [skills/runtime.py](course_agent/skills/runtime.py)：`SkillRegistry`、`@skill` 装饰器、`LocalSkillProvider`
- [skills/builtin.py](course_agent/skills/builtin.py)：2 个内建 Skill Demo
- [cli.py](course_agent/cli.py)：`course-agent skills list`

### 为什么 Skill 先于 MCP 落地？

- 本地、离线、无额外依赖，最好测
- 先解决“高层能力复用”的问题
- 给后续接外部能力前，先把统一 capability 接口磨稳

---

## 🔌 MCP Adapter（实验性，Task 013）

Task 013 没有一上来就强依赖真实 MCP server，而是先走 **mock-first** 路线：默认不启用，不影响任何老功能；启用后可通过统一能力层被 Solver 发现。

### 配置

`config/default.yaml` 新增：

```yaml
mcp:
  enabled: false
  servers:
    - name: demo
      transport: mock
      timeout_s: 15
      enabled: true
```

也可用环境变量临时开启：

```bash
MCP_ENABLED=true uv run course-agent mcp list
```

### 代码入口

- [mcp/config.py](course_agent/mcp/config.py)：`MCPConfig` / `MCPServerConfig`
- [mcp/client.py](course_agent/mcp/client.py)：`MCPClientProvider`
- [mcp/mock_server.py](course_agent/mcp/mock_server.py)：离线可测的 mock MCP tools

### CLI 命令

```bash
uv run course-agent capabilities
uv run course-agent skills list
uv run course-agent mcp list
```

### Chainlit 展示

Task 013 的 Chainlit Step 会按能力来源展示标签：

- `Tool: xxx`
- `Skill: xxx`
- `MCP: demo/xxx`

这样用户能一眼看出这次到底是内部工具在工作，还是系统借了一个 Skill / MCP 外脑。

---

## 🗂️ 项目结构

```
course_agent/
├── core/
│   ├── agent_loop.py     # ReAct 主循环（同步 run + 异步 arun + 回调）
│   └── state.py          # AgentState / AgentCallbacks Protocol
├── llm/
│   ├── base.py           # BaseLLM / LLMMessage / LLMResponse / ToolCall
│   ├── mock.py           # 离线 Rule-based MockLLM
│   ├── openai_like.py    # 真实 OpenAI / OpenAI-兼容 实现（sync + async）
│   └── factory.py        # create_llm(cfg) 工厂
├── tools/
│   ├── registry.py       # @tool 装饰器 + JSON Schema 生成
│   ├── builtin.py        # calculator / file_read / file_write
│   ├── web_tools.py      # 真实 web_search（Tavily / DuckDuckGo）+ web_fetch（trafilatura）
│   ├── python_exec.py    # ✅ Task 008 + 009：沙箱化 Python 执行（4 道安全闸 + extra_packages 白名单装包）
│   ├── pdf_tools.py      # ✅ Task 008 + 009：pdf_read（pypdf 抽文本 + 扫描件 image_ocr 兜底）
│   ├── image_ocr.py      # ✅ Task 009：多模态视觉 OCR（Qwen-VL / GPT-4V / Claude Vision）
│   ├── code_solve.py     # ✅ Task 009：自批改闭环（写→跑→改最多 N 轮，硬上限 5）
│   ├── mistake_book.py   # ✅ Task 010：错题本工具（add_mistake / list_mistakes / review_mistake）
│   ├── kb.py             # ✅ Task 010：教材 RAG（kb_ingest / kb_search 复用 Chroma 独立 collection）
│   └── generator.py      # ✅ Task 011：题目生成器（generate_question，基于错题本+教材 RAG，结构化 JSON）
├── storage/              # ✅ Task 010：本地持久化层
│   └── mistake_db.py     # SQLite 错题库 + SM-2 间隔复习算法
├── ui/
│   ├── chainlit_app.py   # Web UI 入口：场景按钮 + Settings 面板 + 多轮 + 记忆开关
│   └── adapters.py       # AgentCallbacks → Chainlit Step 适配
├── memory/               # ✅ Task 007：会话记忆系统
│   ├── base.py           # MemoryRecord / BaseMemory Protocol
│   ├── embedders.py      # HashEmbedder（离线）/ OpenAIEmbedder（DashScope/OpenAI）
│   ├── short_term.py     # 滑动窗口 + LLM 摘要压缩
│   ├── long_term.py      # Chroma PersistentClient（cosine HNSW）
│   ├── manager.py        # MemoryManager（enrich_context 注入相关记忆）
│   └── tools.py          # @tool recall / remember 工具
├── agent/                # ✅ Task 011 + 012：专用 Agent 角色（多 Agent 编排基石）
│   ├── __init__.py       # 导出 ExaminerAgent / Planner / Solver / Critic / Orchestrator + AgentMessage / BaseAgent
│   ├── base.py           # ✅ Task 012：BaseAgent Protocol + AgentMessage（多 Agent 通信契约）
│   ├── examiner.py       # ExaminerAgent：限定工具集 + 独立 system_prompt 的 AgentLoop 包装；Task 012 起判分可委托给 CriticAgent
│   ├── planner.py        # ✅ Task 012：PlannerAgent（拆 sub_tasks，工具白名单仅 kb_search/list_mistakes，强制 JSON）
│   ├── solver.py         # ✅ Task 012：SolverAgent（执行单个 sub_task，全工具集）
│   ├── critic.py         # ✅ Task 012：CriticAgent（独立评审，工具白名单仅 kb_search，输出 {score, pass, feedback}）
│   └── orchestrator.py   # ✅ Task 012：Orchestrator（Plan→Solve→Critique→Refine 闭环；硬上限 30 LLM 调用）
├── runtime/              # ✅ Task 014：统一运行时入口（legacy / langgraph）
│   ├── __init__.py       # create_runtime 统一导出
│   ├── backend.py        # backend 选择器
│   ├── legacy_runtime.py # 兼容旧 Orchestrator 的薄封装
│   ├── langgraph_runtime.py
│   │                     # LangGraph Runtime（checkpoint / graph invoke / mermaid）
│   ├── langchain_adapters.py
│   │                     # BaseLLM / Tool / Capability 到 LangChain 的桥接层
│   └── state.py          # GraphRuntimeState / state_to_result / trace helper
├── graph/                # ✅ Task 014：LangGraph 节点、边与图构建
│   ├── __init__.py
│   ├── orchestrator_graph.py
│   │                     # Planner→Solver→Critic→Refine 图构建
│   ├── nodes.py          # 节点实现
│   ├── edges.py          # 条件边判定
│   └── prompts.py        # Mermaid fallback / 图常量
├── capabilities/         # ✅ Task 013：统一能力层（internal_tool / skill / mcp）
│   ├── base.py           # CapabilityKind / CapabilitySpec / CapabilityCallResult / BaseCapabilityProvider
│   ├── registry.py       # CapabilityRegistry
│   ├── router.py         # CapabilityRouter（按 Agent 收口能力）
│   └── adapters.py       # ToolRegistry / Skill / MCP 的 provider 与工具视图适配
├── skills/               # ✅ Task 013：本地 Skill Runtime
│   ├── runtime.py        # SkillRegistry / @skill / LocalSkillProvider
│   ├── builtin.py        # study_plan_skill / quiz_from_notes_skill
│   └── registry.py       # 兼容导出
├── mcp/                  # ✅ Task 013：MCP Adapter（mock-first）
│   ├── config.py         # MCPConfig / MCPServerConfig
│   ├── client.py         # MCPClientProvider
│   └── mock_server.py    # 离线可测的 mock MCP tools
├── observability/        # ✅ Task 012：可观测性（SQLite metrics）
│   ├── __init__.py
│   └── metrics.py        # Task 012/013/014：LLM + capability metrics，支持 runtime_backend 维度
├── context/              # 🔜 Prompt 模板 / 上下文压缩
├── orchestrator/         # ⛔ 改在 agent/orchestrator.py（保留空目录占位以兼容旧 import 路径）
├── config.py             # Pydantic 配置 + .env 加载
├── logger.py             # loguru 包装
└── cli.py                # typer + rich 的 CLI 入口（chat / tools / version / ui / doctor / metrics / capabilities / skills / mcp）

tests/                    # 357 passed + 6 skipped：新增 Task 014 runtime / graph / adapters / CLI / Chainlit 回归测试
config/default.yaml       # 默认 YAML 配置
.chainlit/config.toml     # Chainlit 主题/UI 配置
chainlit.md               # Chainlit 欢迎页
.env.example              # 环境变量模板（API Key 占位符 + 5 家 Provider 示例）
.python-version           # 锁定 Python 3.13
data/memory/              # 长期记忆持久化目录（已加入 .gitignore，每会话一个子目录）
```

---

## 🛠️ 故障排查（FAQ）

<details>
<summary><strong>Q1: 打开 http://localhost:8000 是一片空白。</strong></summary>

**原因**：你大概率在用 Python 3.14。Chainlit 依赖的 anyio/starlette 对 3.14 适配未完成，前端静态资源会 500。

**解决**：按照 [🐍 Python 版本要求](#-python-版本要求) 切换到 3.13，然后：
```bash
rm -rf .venv
pkill -9 -f "chainlit run"   # 清掉旧进程（重要！）
uv sync --extra dev
uv run course-agent ui
```
</details>

<details>
<summary><strong>Q2: 报错 <code>[LLM 认证失败] 请检查 OPENAI_API_KEY</code></strong></summary>

按以下顺序排查：

1. **验证 Key 本身是否有效**：
   ```bash
   curl -s https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"qwen-plus","messages":[{"role":"user","content":"ping"}]}'
   ```
2. **确认 `.env` 文件在项目根目录**，不是在子目录。
3. **确认 `OPENAI_BASE_URL` 和 Key 匹配**（DashScope Key 不能配 DeepSeek 的 URL，反之亦然）。
4. **如果你重建过 venv**，一定要先 `pkill -9 -f "chainlit run"` 再启动，否则旧进程仍在跑旧代码。
</details>

<details>
<summary><strong>Q3: 端口 8000 被占用</strong></summary>

```bash
lsof -i :8000 -sTCP:LISTEN -t | xargs kill -9   # 释放端口
# 或直接换端口
uv run course-agent ui --port 9000
```
</details>

<details>
<summary><strong>Q4: 我不想用 uv，能用 pip 吗？</strong></summary>

可以。先确保你在 Python 3.11~3.13 环境下：
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
course-agent ui
```
但我们**强烈推荐 uv**——它会自动管理 Python 版本、锁文件、虚拟环境，比 pip 快 10x 以上。
</details>

<details>
<summary><strong>Q5: 我想加自己的工具/Provider，从哪里入手？</strong></summary>

- **加工具**：在 `course_agent/tools/` 下新建文件，用 `@tool(...)` 装饰一个普通 Python 函数即可。参考 [builtin.py](course_agent/tools/builtin.py) 的 `calculator` 实现。
- **加 Provider**：在 `course_agent/llm/` 下实现一个继承自 `BaseLLM` 的类（参考 `openai_like.py`），然后在 `factory.py` 的 `create_llm` 加一个分支。
</details>

---

## 📖 设计文档

项目以「Task 驱动」方式迭代开发，每个 Task 都有对应的设计方案：

- [`task/task_001.md`](task/task_001.md) — 初始需求
- [`task/task_002.md`](task/task_002.md) — 总体方案（Milestone 1 架构设计）
- [`task/task_003.md`](task/task_003.md) — 接入真实 LLM 方案
- [`task/task_004.md`](task/task_004.md) — Web UI 开发方案
- [`task/task_005.md`](task/task_005.md) — Bug 报告归档
- [`task/task_006.md`](task/task_006.md) — 文档重整需求（即本次）
- [`task/task_007.md`](task/task_007.md) — 记忆系统 + 真实 Web 检索方案 ✅
- [`task/task_008.md`](task/task_008.md) — 让 Agent 真正动手做作业（python_exec / pdf_read / doctor）✅
- [`task/task_009.md`](task/task_009.md) — 让 Agent「看见」+「自己批改」（image_ocr / code_solve / extra_packages）✅
- [`task/task_010.md`](task/task_010.md) — 让 Agent「记得住错」+「翻得到书」（错题本 + 教材 RAG）✅
- [`task/task_011.md`](task/task_011.md) — 让 Agent「答得顺」+「考得出」（流式 + Examiner Agent + generate_question）✅
- [`task/task_012.md`](task/task_012.md) — 让 Agent「分工合作」+「看得见账」（多 Agent + metrics + data layer）✅
- [`task/task_013.md`](task/task_013.md) — 让 Agent「会借外脑」（Capability Layer + Skill Runtime + MCP Adapter）✅

---

## 🤝 贡献 & 下一步

**当前最需要**：
- 🛠️ 更多工具：`python_exec`（沙箱执行代码）、`pdf_read`、`image_ocr`
- 👥 Multi-Agent（Milestone 3）：Planner / Executor / Grader 角色分工
- 🧪 长期记忆的清理 / 摘要 / TTL 策略
- 🌐 更多检索 Provider：Brave Search、SerpAPI

**开发规范**：
- 修改代码后必须通过 `uv run pytest` 和 `uv run ruff check .`
- 新增功能尽量附带单元测试（参考 [tests/](tests/)）
- 涉及外部 LLM 调用的新测试放在 `test_*_live.py` 并用 `RUN_LIVE_LLM=1` gate 住

---

## 📜 License

MIT
