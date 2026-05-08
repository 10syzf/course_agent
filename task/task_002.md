# Course Agent 项目方案文档

## 一、项目概述

### 1.1 项目名称
**Course Agent** —— 面向学生课程作业场景的智能 Agent 系统

### 1.2 项目目标
构建一套可扩展、可复用的多 Agent 系统，帮助学生完成课程作业相关的任务，包括：
- 作业内容理解与拆解
- 资料检索与知识问答
- 代码/文档/数学题的辅助完成
- 作业进度管理与提醒
- 学习过程记忆与个性化辅导

### 1.3 核心诉求
本项目强调 **Agent 工程化能力**，需综合运用以下关键技术：
- **Agent Loop（推理-行动循环）**
- **Context 管理（上下文工程）**
- **Memory 系统（短期 + 长期记忆）**
- **Tool Use（工具调用）**
- **多 Agent 协作（可选扩展）**

---

## 二、总体架构设计

### 2.1 架构分层

```
┌──────────────────────────────────────────────────────┐
│                    用户交互层 (UI/CLI)                 │
│          Web UI / CLI / API (FastAPI)                │
└──────────────────────────────────────────────────────┘
                          ↕
┌──────────────────────────────────────────────────────┐
│                    Agent 编排层                        │
│   Orchestrator / Planner / Router (多 Agent 调度)     │
└──────────────────────────────────────────────────────┘
                          ↕
┌──────────────────────────────────────────────────────┐
│                    核心 Agent 层                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ 作业分析 │ │ 资料检索 │ │ 代码助手 │ │ 写作助手│ │
│  │  Agent   │ │   Agent  │ │   Agent  │ │  Agent  │ │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘ │
└──────────────────────────────────────────────────────┘
                          ↕
┌──────────────────────────────────────────────────────┐
│                Agent Loop 核心引擎                     │
│   Perceive → Think → Plan → Act → Observe → Reflect  │
└──────────────────────────────────────────────────────┘
                          ↕
┌──────────────────────────────────────────────────────┐
│               能力支撑层                               │
│  Context Mgr │ Memory System │ Tool Registry │ LLM   │
└──────────────────────────────────────────────────────┘
                          ↕
┌──────────────────────────────────────────────────────┐
│                基础设施层                              │
│   Vector DB (Chroma) │ SQLite │ FileStore │ Cache    │
└──────────────────────────────────────────────────────┘
```

### 2.2 核心模块划分
| 模块 | 职责 |
| --- | --- |
| `agent/` | 各类 Agent 的实现（base、作业分析、检索、代码、写作等） |
| `core/` | Agent Loop 核心引擎、状态机、调度器 |
| `context/` | 上下文管理：prompt 模板、会话窗口、token 压缩 |
| `memory/` | 短期/长期记忆、向量记忆、记忆检索与反思 |
| `tools/` | 工具定义与注册（文件读写、网页搜索、代码执行、计算器等） |
| `llm/` | LLM 适配器（OpenAI/本地模型/DeepSeek/Qwen 等） |
| `orchestrator/` | 多 Agent 协作与路由 |
| `api/` | FastAPI 对外接口 |
| `ui/` | 前端/CLI 入口 |
| `config/` | 配置管理 |
| `tests/` | 单元测试与集成测试 |

---

## 三、关键技术方案

### 3.1 Agent Loop（核心执行循环）

采用 **ReAct + Reflection** 混合范式：

```
while not done and step < max_steps:
    1. Perceive   —— 获取当前输入 + 上下文 + 记忆
    2. Think      —— LLM 推理，产出 Thought
    3. Plan       —— 决定下一步 Action（调用 Tool / 回答 / 继续思考）
    4. Act        —— 执行 Action（Tool 调用）
    5. Observe    —— 收集 Tool 返回结果，更新上下文
    6. Reflect    —— 判断是否完成任务，必要时修正计划
```

**关键实现点：**
- 统一的 `AgentState` 数据结构（messages、scratchpad、tool_calls、step_count）
- 支持 **streaming**（边推理边输出）
- 支持 **max_steps / timeout / token_budget** 限制防止死循环
- 每步产生 trace，便于调试与可视化

### 3.2 Context 管理（上下文工程）

- **Prompt 模板分层**：System Prompt（角色定义） + Task Prompt（任务描述） + Tool Schema + History + Memory Recall
- **滑动窗口**：按 token 数量截断历史对话
- **上下文压缩**：超长对话使用 LLM 做 summarize（分段摘要 + 关键信息提取）
- **结构化上下文**：课程信息、作业元数据、截止时间等作为结构化字段注入，而非纯文本

### 3.3 记忆系统（Memory）

分三层设计：

| 层级 | 存储 | 用途 |
| --- | --- | --- |
| **Working Memory** | 内存 / 会话对象 | 单轮任务内的临时状态（scratchpad） |
| **Short-term Memory** | SQLite / Redis | 最近 N 轮对话、当前作业上下文 |
| **Long-term Memory** | 向量数据库 (Chroma/FAISS) | 学生画像、历史作业、知识点偏好、易错点 |

**关键能力：**
- `memory.save(content, metadata, type)` —— 写入（自动 embedding）
- `memory.retrieve(query, top_k)` —— 向量相似度检索
- `memory.reflect()` —— 定期反思，将短期记忆提炼为长期记忆（类似 Generative Agents）
- **Episodic + Semantic** 两类记忆并存

### 3.4 Tool 系统

基于 **OpenAI Function Calling / JSON Schema** 风格统一工具定义：

```python
@tool(name="search_web", description="...")
def search_web(query: str) -> str: ...
```

**初版内置工具：**
| 工具 | 说明 |
| --- | --- |
| `file_read` / `file_write` | 读写本地作业文件 |
| `web_search` | 联网检索资料（DuckDuckGo / Bing） |
| `web_fetch` | 抓取网页正文 |
| `python_exec` | 在沙箱中执行 Python 代码 |
| `calculator` | 数学表达式求值 |
| `pdf_reader` | 解析 PDF 教材 / 作业文档 |
| `rag_query` | 对课程资料库做 RAG 检索 |
| `submit_answer` | 提交最终答案给用户/系统 |

**Tool Registry**：支持动态注册、按 Agent 分配可用工具子集。

### 3.5 LLM 适配层
- 抽象 `BaseLLM` 接口（`chat` / `stream` / `embed`）
- 至少适配 2 个 provider：**OpenAI 兼容接口**（含 DeepSeek、Qwen、本地 Ollama）+ **Anthropic**（可选）
- 支持结构化输出（JSON Mode / Tool Calling）

### 3.6 多 Agent 协作（进阶）
- **Planner Agent**：将用户作业需求拆解为子任务
- **Router**：根据子任务类型分派给专门 Agent（代码/写作/检索）
- **Critic Agent**：对产出做质量评审，不合格则打回
- 通信采用消息总线（内存队列即可，后续可换 Redis Pub/Sub）

---

## 四、目录结构规划

```
course_agent/
├── README.md
├── pyproject.toml          # 使用 uv / poetry 管理
├── .env.example
├── config/
│   └── default.yaml
├── course_agent/
│   ├── __init__.py
│   ├── core/
│   │   ├── agent_loop.py
│   │   ├── state.py
│   │   └── scheduler.py
│   ├── agent/
│   │   ├── base.py
│   │   ├── homework_agent.py
│   │   ├── research_agent.py
│   │   ├── code_agent.py
│   │   └── writing_agent.py
│   ├── context/
│   │   ├── manager.py
│   │   ├── prompt.py
│   │   └── compressor.py
│   ├── memory/
│   │   ├── base.py
│   │   ├── short_term.py
│   │   ├── long_term.py
│   │   └── reflector.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── file_tools.py
│   │   ├── web_tools.py
│   │   ├── code_tools.py
│   │   └── rag_tools.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── openai_like.py
│   │   └── ollama.py
│   ├── orchestrator/
│   │   ├── planner.py
│   │   └── router.py
│   ├── api/
│   │   └── server.py       # FastAPI
│   └── cli.py              # typer/rich CLI
├── data/
│   ├── vector_db/
│   └── sqlite.db
├── tests/
└── task/
    ├── task_001.md
    └── task_002.md
```

---

## 五、技术选型

| 类别 | 选型 | 理由 |
| --- | --- | --- |
| 语言 | Python 3.11+ | Agent 生态成熟 |
| 依赖管理 | `uv` 或 `poetry` | 现代化 |
| LLM SDK | `openai` 官方 SDK | 兼容 DeepSeek/Qwen 等 |
| 向量库 | `chromadb`（本地优先） | 轻量、无需部署 |
| Embedding | `bge-small-zh` / OpenAI `text-embedding-3-small` | 中英兼顾 |
| 数据库 | `SQLite` + `SQLAlchemy` | 零部署 |
| Web 框架 | `FastAPI` + `uvicorn` | 异步、类型友好 |
| CLI | `typer` + `rich` | 体验好 |
| 日志 | `loguru` | 简洁 |
| 测试 | `pytest` | 标准 |
| 代码执行沙箱 | `subprocess` + 资源限制（后续可上 `e2b`） | MVP 够用 |
| 配置 | `pydantic-settings` + yaml | 类型安全 |

> 不引入 LangChain/LangGraph，保持轻量与可控；仅在必要处参考其思想。

---

## 六、开发里程碑

### Milestone 1：MVP 骨架（基础可跑通）
- [ ] 项目脚手架、配置、日志、LLM 适配
- [ ] 最小 Agent Loop（ReAct）
- [ ] Tool Registry + 3 个基础工具（file / calc / web_search）
- [ ] CLI 入口，支持单轮对话 + 工具调用

### Milestone 2：上下文与记忆
- [ ] Prompt 模板系统
- [ ] 短期记忆（会话历史 + 窗口）
- [ ] 长期记忆（Chroma + 写入/检索）
- [ ] 上下文压缩（摘要）

### Milestone 3：作业场景 Agent
- [ ] Homework Agent：解析作业、拆子任务
- [ ] Research Agent：RAG + web_search
- [ ] Code Agent：代码生成 + 执行 + 自我修正
- [ ] Writing Agent：论文/报告辅助

### Milestone 4：多 Agent 编排
- [ ] Planner + Router
- [ ] Critic / Reflection
- [ ] 记忆反思机制

### Milestone 5：对外服务 & 打磨
- [ ] FastAPI 接口 + SSE 流式
- [ ] 简单 Web UI（可选 Streamlit）
- [ ] 完整测试覆盖
- [ ] 使用文档

---

## 七、关键风险与应对

| 风险 | 应对 |
| --- | --- |
| LLM 幻觉导致作业错误 | 工具调用优先、RAG 引用来源、Critic 校验 |
| 长对话 token 爆炸 | 滑动窗口 + 分段摘要 + 向量召回 |
| 工具执行安全（代码执行） | 子进程 + 超时 + 资源限制 + 白名单 |
| Agent 死循环 | max_steps + token_budget + 早停策略 |
| 多 Agent 协作复杂度 | 先单 Agent 跑通，再渐进引入编排 |

---

## 八、验收标准
1. 学生可通过 CLI/API 提交一道课程作业描述，Agent 能自动完成分析→检索→作答→输出全流程。
2. 具备多轮对话能力，记住上下文与历史作业偏好。
3. 至少支持 5 种工具的自动调用。
4. 向量记忆可在新会话中被检索并影响回答。
5. 代码有清晰模块划分、单元测试覆盖核心模块、可一键启动。

---

> 后续开发将以本方案为蓝本，按 Milestone 推进，每完成一个里程碑产出对应 `task_00X.md` 任务单。
