# Task 004：Course Agent Web UI 开发方案

> 目标：为 Course Agent 增加一个**漂亮的浏览器 Web UI**，替代纯 CLI 交互，提升作业辅导场景的使用体验。

## 一、项目背景与目标

### 1.1 背景
当前项目只有 CLI 入口（`uv run course-agent chat "..."`），问题：
- 单次问答、无历史
- 纯文本输出，Markdown/LaTeX/代码块体验差
- 无法展示 Agent 中间思考过程
- 不方便分享给同学或老师演示

### 1.2 目标
- 浏览器打开一个现代化的聊天界面（类 ChatGPT 体验）
- **流式输出**：边思考边显示
- **可视化 Agent Trace**：清晰看到每一步思考、工具调用、工具结果
- **多轮对话 + 历史**：会话持久化，可回看
- **作业场景增强**：课程选择、作业模板、快捷提问
- **Markdown / LaTeX / 代码高亮**原生支持
- 不依赖额外前端构建（不引入 React/Vue 工具链）

### 1.3 验收标准
1. [ ] `uv run course-agent-ui` 一条命令即可启动 Web 服务
2. [ ] 浏览器打开 `http://localhost:8000` 看到精美聊天界面
3. [ ] 能流式打字机效果接收 LLM 输出
4. [ ] 每次工具调用在对话流中以「步骤卡片」形式展示
5. [ ] 支持 5 轮以上的多轮对话，刷新页面历史仍在
6. [ ] Markdown / LaTeX / Python 代码块渲染正确
7. [ ] 可通过界面切换 provider（openai / mock）和 model
8. [ ] 现有 CLI 不受影响，测试全绿

---

## 二、技术选型

### 2.1 前端框架：Chainlit
**选择理由：**
- 纯 Python 开发，**不引入前端构建工具链**（省去 node_modules / webpack 负担）
- 开箱即用的 ChatGPT 风格 UI（消息气泡、流式输出、Markdown、LaTeX、代码高亮）
- 原生支持「Step」组件可视化 Agent 思考链
- 自带会话持久化（SQLite / 文件）
- 部署简单（一个命令起服务）
- 与 Python Agent 库天然契合，不像 Streamlit 需要重跑脚本

**对比方案：**
| 方案 | 开发成本 | UI 美观 | 流式 | Trace 可视化 | 结论 |
|---|---|---|---|---|---|
| Chainlit | 低 | 高 | ✅ | ✅ 原生 Step | **✅ 选用** |
| Streamlit | 低 | 中 | 需 hack | 弱 | ❌ |
| FastAPI + 原生 HTML | 中 | 中（需自己调） | ✅ | 需手写 | 备选 |
| FastAPI + React | 高 | 高 | ✅ | 强 | ❌（工作量过大） |

### 2.2 依赖
- `chainlit>=1.1`（核心）
- 继续使用已有的 `openai` / `pydantic` / `loguru` 等

### 2.3 文件结构（新增）
```
course_agent/
├── ui/
│   ├── __init__.py
│   ├── chainlit_app.py        # Chainlit 主入口
│   ├── adapters.py            # AgentLoop ↔ Chainlit 适配器
│   └── public/
│       └── favicon.ico        # 可选：自定义图标
├── cli.py                      # 新增 `course-agent-ui` 子命令
└── .chainlit/                  # Chainlit 配置
    └── config.toml
```

---

## 三、核心功能设计

### 3.1 交互流程

```
用户输入
    ↓
Chainlit 收到 on_message
    ↓
启动 AgentLoop（传入 Chainlit 回调）
    ↓
每一步：
  - LLM 思考  → cl.Message(content=..., author="assistant") 流式更新
  - 工具调用  → cl.Step(name=tool_name, type="tool") 展开
  - 工具结果  → 同一 Step 内显示 result
    ↓
最终答案    → cl.Message(content=final, author="assistant")
```

### 3.2 Agent Loop 改造要点

**目标**：不破坏现有 `AgentLoop.run()` 接口，增加 **可选回调钩子** 以便 UI 层订阅事件。

在 [course_agent/core/agent_loop.py](course_agent/core/agent_loop.py) 新增：

```python
class AgentCallbacks(Protocol):
    async def on_thought(self, step: int, content: str) -> None: ...
    async def on_tool_call(self, step: int, name: str, args: dict) -> None: ...
    async def on_tool_result(self, step: int, name: str, result: str) -> None: ...
    async def on_final(self, answer: str) -> None: ...

class AgentLoop:
    async def arun(self, user_input: str, callbacks: AgentCallbacks | None = None) -> AgentResult:
        """异步版本，支持回调。原 run() 保持同步不变。"""
```

**设计原则：**
- 原 `run()` 同步接口**保持不变** → CLI 和测试不受影响
- 新增 `arun()` 异步版本，内部遇到思考/工具调用时触发回调
- 回调是 optional，None 时行为等同于 `run()`

### 3.3 Chainlit 适配器

`course_agent/ui/chainlit_app.py` 核心伪代码：

```python
import chainlit as cl
from course_agent.core import AgentLoop
from course_agent.llm import create_llm

@cl.on_chat_start
async def start():
    llm = create_llm()
    cl.user_session.set("agent", AgentLoop(llm=llm))
    cl.user_session.set("history", [])
    await cl.Message(
        content="👋 你好！我是 Course Agent，帮你完成课程作业。试试问我一道数学题或知识点吧。"
    ).send()

@cl.on_message
async def on_message(msg: cl.Message):
    agent: AgentLoop = cl.user_session.get("agent")
    callbacks = ChainlitCallbacks()
    result = await agent.arun(msg.content, callbacks=callbacks)
    # final 已在回调内发送
```

`ChainlitCallbacks` 负责把 Agent 事件翻译成 Chainlit UI：
- `on_thought` → 更新主消息
- `on_tool_call` + `on_tool_result` → 创建/关闭 `cl.Step`
- `on_final` → 发送最终 `cl.Message`

### 3.4 多轮对话 & 历史持久化
- 利用 `cl.user_session` 存储 `AgentLoop` 实例与历史消息
- 会话消息列表在调用 `arun` 时作为上下文传入
- Chainlit 自带 SQLite 持久化（可选开启 `chainlit.config.toml` 的 `data_layer`）

### 3.5 作业场景增强（进阶，可选）

**起始屏幕添加快捷按钮：**
```python
actions = [
    cl.Action(name="math", value="math", label="📐 数学作业"),
    cl.Action(name="code", value="code", label="💻 编程作业"),
    cl.Action(name="write", value="write", label="📝 写作作业"),
    cl.Action(name="research", value="research", label="🔍 资料检索"),
]
```
点击对应 action 自动注入专属 System Prompt。

**Settings 面板：**
- Model 下拉（qwen-plus / qwen-turbo / qwen-max）
- Temperature 滑块
- Max steps 输入

### 3.6 Trace 可视化示例

最终界面示意：
```
┌─────────────────────────────────────────┐
│ 👤 用户：帮我算 (12+8)*5 等于多少        │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ 🤖 Course Agent                          │
│                                          │
│ ▶ 🔧 Step 1: 调用工具 calculator   [+]   │
│      参数: {expression: "(12+8)*5"}      │
│      结果: (12+8)*5 = 100                │
│                                          │
│ 计算结果是：                             │
│ (12+8)×5 = 20×5 = **100**                │
│ 答案是 **100**。                         │
└─────────────────────────────────────────┘
```

---

## 四、实施步骤

### Step 1：依赖与脚手架
- [ ] `pyproject.toml` 添加 `chainlit>=1.1` 到默认依赖
- [ ] `uv sync` 安装
- [ ] 创建 `course_agent/ui/` 目录与骨架文件
- [ ] 创建 `.chainlit/config.toml` 基础配置（应用名、主题、logo）

### Step 2：Agent Loop 异步化 & 回调机制
- [ ] 在 `state.py` 中定义 `AgentCallbacks` Protocol
- [ ] `AgentLoop.arun()` 实现：异步执行 + 触发回调
- [ ] `llm/openai_like.py` 增加 `achat()` 异步方法（使用 `openai.AsyncOpenAI`）
- [ ] `llm/mock.py` 的 `achat()` 直接 await 同步逻辑
- [ ] 单元测试：`test_agent_loop_async.py`

### Step 3：Chainlit 适配器
- [ ] 实现 `chainlit_app.py` 的 `on_chat_start` / `on_message`
- [ ] 实现 `adapters.py` 中的 `ChainlitCallbacks`
- [ ] 启动命令：新增 `cli.py` 的 `ui` 子命令 → `chainlit run course_agent/ui/chainlit_app.py`

### Step 4：多轮对话
- [ ] 会话历史存于 `cl.user_session`
- [ ] `arun()` 支持接收历史消息列表
- [ ] 测试：连续 3 轮对话能记住上下文

### Step 5：Trace 可视化
- [ ] 每次工具调用 → 创建 `cl.Step`
- [ ] 支持折叠/展开
- [ ] 错误时 Step 标红

### Step 6：作业场景增强（可选）
- [ ] 起始屏 Action 按钮
- [ ] 每个 Action 对应的 System Prompt 模板
- [ ] Settings 面板：切换 model / temperature

### Step 7：美化与打磨
- [ ] 自定义 logo / favicon
- [ ] 欢迎语配置
- [ ] 主题色（浅色 + 深色）
- [ ] 响应式适配（手机浏览器可用）

### Step 8：测试与文档
- [ ] 单元测试覆盖 async 代码
- [ ] README 添加"启动 Web UI"章节
- [ ] 录一个 GIF 演示（可选）

---

## 五、风险与应对

| 风险 | 应对 |
|---|---|
| Chainlit 版本 API 变动 | 固定 `chainlit>=1.1,<2.0`，锁定 uv.lock |
| OpenAI 同步 SDK 与 async 事件循环冲突 | 使用 `openai.AsyncOpenAI` 异步客户端 |
| 工具执行是同步阻塞（如 `calculator`） | 用 `asyncio.to_thread()` 包装同步工具 |
| 会话历史无限增长导致 token 爆炸 | 简单截断（保留最近 10 轮）；后续 Milestone 2 的压缩机制可无缝接入 |
| 并发用户（多标签）session 串 | Chainlit 原生按 session_id 隔离，使用 `cl.user_session` 即可 |
| 端口占用 | `course-agent ui --port 9000` CLI 参数覆盖 |

---

## 六、交付物清单

- [ ] `course_agent/ui/chainlit_app.py`
- [ ] `course_agent/ui/adapters.py`
- [ ] `.chainlit/config.toml`
- [ ] `course_agent/core/agent_loop.py` 新增 `arun()` + 回调接口
- [ ] `course_agent/llm/openai_like.py` 新增 `achat()`
- [ ] `course_agent/llm/mock.py` 新增 `achat()`
- [ ] `course_agent/cli.py` 新增 `ui` 子命令
- [ ] `tests/test_agent_loop_async.py`
- [ ] `pyproject.toml` 加 `chainlit` 依赖
- [ ] `README.md` 更新启动说明与截图

---

## 七、启动方式（开发完成后）

```bash
# 一键启动 Web UI
uv run course-agent ui

# 或指定端口
uv run course-agent ui --port 9000

# 浏览器打开
open http://localhost:8000
```

---

## 八、目录结构快览（完成后）

```
course_agent/
├── agent/
├── context/
├── core/
│   ├── agent_loop.py    ← 新增 arun() + 回调
│   └── state.py         ← 新增 AgentCallbacks Protocol
├── llm/
│   ├── base.py          ← 新增 async chat 抽象
│   ├── mock.py          ← 新增 achat
│   └── openai_like.py   ← 新增 achat (AsyncOpenAI)
├── memory/
├── orchestrator/
├── tools/
├── ui/                   ← 🆕 Web UI 模块
│   ├── __init__.py
│   ├── chainlit_app.py
│   ├── adapters.py
│   └── public/
├── cli.py                ← 新增 ui 子命令
├── config.py
└── logger.py
.chainlit/
└── config.toml
```

---

## 九、预计工作量与里程碑

| Step | 工作量 | 关键交付 |
|---|---|---|
| Step 1 | 小 | 依赖 + 骨架 |
| Step 2 | 中 | arun + 回调机制 |
| Step 3 | 中 | Chainlit 基础可用 |
| Step 4 | 小 | 多轮对话 |
| Step 5 | 中 | Trace 可视化 |
| Step 6 | 可选 | 场景增强 |
| Step 7 | 小 | 美化 |
| Step 8 | 小 | 测试文档 |

---

## 十、后续演进

本 Task 完成后，项目将具备完整的**本地可视化使用能力**，下一步自然衔接：
- Task 005：记忆系统（短期 / 长期）— UI 会多一个"记忆浏览器"
- Task 006：多 Agent 编排（UI 可展示不同 Agent 的角色切换）
- Task 007：对外部署（Docker + 反向代理 + HTTPS）

---

> 完成本 Task 后，Course Agent 将从"CLI 工具"升级为"Web 产品雏形"，可以直接分享给同学使用或做课堂演示。
