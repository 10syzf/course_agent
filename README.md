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

## ✅ 当前进度

| 里程碑 | 状态 | 内容 |
|---|---|---|
| Milestone 1 · MVP 骨架 | ✅ | Agent Loop、工具系统、CLI、配置、MockLLM |
| Task 003 · 接入真实 LLM | ✅ | OpenAI SDK + AsyncOpenAI + 限流重试 + 错误分类 |
| Task 004 · 浏览器 Web UI | ✅ | Chainlit + Step 可视化 + 多轮 + 场景按钮 + Settings 面板 |
| **Task 007 · 记忆系统 + 真实检索** | ✅ | **短期滑动窗口 + LLM 摘要压缩；长期 Chroma 向量库；recall/remember 工具；Tavily/DuckDuckGo + trafilatura 真实联网** |
| Milestone 3 · 多 Agent 编排 | 🔜 | 规划者 / 执行者 / 批改者分工 |

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
- ⚡ 流式输出（打字机效果）
- 🔧 **工具调用以可折叠 Step 卡片展示**——每一步 Agent 干了什么都清清楚楚
- 💬 多轮对话（会话级保留最近 10 轮）
- 🎯 **作业场景快捷按钮**：📐 数学 / 💻 编程 / 📝 写作 / 🔍 资料检索，一键切换专属 System Prompt
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

**当前测试状态**：54 passed + 5 skipped（live tests 默认跳过；含 `RUN_LIVE_WEB=1` 触发的真实 DuckDuckGo / web_fetch 联网测试）。

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
│   └── web_tools.py      # 真实 web_search（Tavily / DuckDuckGo）+ web_fetch（trafilatura）
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
├── agent/                # 🔜 Milestone 3：专用 Agent 角色
├── context/              # 🔜 Prompt 模板 / 上下文压缩
├── orchestrator/         # 🔜 Milestone 3：多 Agent 编排
├── config.py             # Pydantic 配置 + .env 加载
├── logger.py             # loguru 包装
└── cli.py                # typer + rich 的 CLI 入口

tests/                    # 54 passed + 5 skipped：tools / agent_loop / config / llm / async / memory_* / web_tools
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
