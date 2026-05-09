# Task 007：Course Agent 下一阶段开发规划

> 本 Task 基于 Milestone 1（MVP 骨架） + Task 003（真实 LLM）+ Task 004（Web UI）完成后的项目现状，规划**下一阶段最值得开发的方向**，并挑选其中一个作为本期主攻点落地。

---

## 一、当前项目现状盘点

### 1.1 已具备的能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | `run()` 同步 + `arun()` 异步 + 回调机制 |
| LLM 抽象层 | ✅ | `BaseLLM` / `MockLLM` / `OpenAILLM`（兼容 DashScope / DeepSeek / 豆包 / OpenAI） |
| Tool Registry | ✅ | `@tool` 装饰器 + JSON Schema 自动生成 |
| 内置工具 | ✅ | `calculator` / `file_read` / `file_write` / `web_search`（mock） |
| CLI | ✅ | `chat` / `tools` / `version` / `ui` |
| Web UI | ✅ | Chainlit + Step 可视化 + 多轮 + 场景按钮 + Settings 面板 |
| 测试与 Lint | ✅ | 24 passed + 3 skipped；ruff clean |
| Python 环境 | ✅ | 锁定 3.13，`.python-version` + `pyproject.toml` 限制 `<3.14` |

### 1.2 明显的缺口（代码中的 "空包" 与 mock）

| 缺口 | 当前状态 | 影响 |
|---|---|---|
| `course_agent/memory/` | **空 `__init__.py`** | 刷新浏览器会话历史就丢；跨 session 记忆完全没有 |
| `course_agent/context/` | **空 `__init__.py`** | 没有 prompt 模板管理、没有上下文压缩策略 |
| `course_agent/orchestrator/` | **空 `__init__.py`** | 只有一个 Agent，不能分工协作 |
| `web_search` | **Mock 返回硬编码字符串** | 检索场景名不副实，无法真正查资料 |
| 工具种类 | **仅 4 个** | 作业场景下常见的「运行代码 / 读 PDF / 画图 / OCR」都缺失 |
| 会话持久化 | **未开启 Chainlit data layer** | 刷新页面=丢历史，无法回看 |
| 错误可观测性 | **只打 loguru 日志** | UI 上看不到耗时 / token 消耗 / 失败统计 |
| 部署 | **仅本地运行** | 没有 Dockerfile、没有生产化部署文档 |

---

## 二、候选开发方向（脑暴 + 评估）

我列了 **8 个候选方向**，按「价值 / 成本 / 与当前项目契合度」打分：

| # | 方向 | 价值 | 成本 | 与现有代码契合度 | 综合 |
|---|---|---|---|---|---|
| **1** | **Memory 记忆系统**（会话持久化 + 短期摘要 + 长期向量检索） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐（`memory/` 已预留） | ⭐⭐⭐⭐⭐ |
| **2** | 真实 `web_search` 工具（Tavily / SerpAPI / Bing） | 🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **3** | `python_exec` 沙箱执行工具（Docker / subprocess + resource limit） | 🔥🔥🔥🔥🔥 | 中高 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **4** | `pdf_read` / `image_ocr`（读作业 PDF / 手写题拍照） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **5** | 多 Agent 编排（Planner / Executor / Grader） | 🔥🔥🔥 | 高 | ⭐⭐⭐（依赖 Memory） | ⭐⭐⭐ |
| **6** | 流式响应（真正的 token-by-token streaming 进 Chainlit） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **7** | 可观测性（Trace 面板 + token 统计 + 时延图） | 🔥🔥🔥 | 中 | ⭐⭐⭐ | ⭐⭐⭐ |
| **8** | 生产化部署（Dockerfile + docker-compose + HTTPS 反代） | 🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 2.1 挑选逻辑

- **#1 Memory** 是 [task/task_002.md](task_002.md) 原始架构承诺之一，目录也预留了，不做就是技术债；且它是 #5 多 Agent 的**前置依赖**。
- **#2 真实 `web_search`** 是 4 大作业场景里「🔍 资料检索」的核心能力，目前 mock 让这个场景名存实亡，成本最低、价值最高。
- **#3 `python_exec`** 对「💻 编程作业」场景是杀手级：可以让 Agent 自己跑代码验证，而不是凭想象写。但沙箱安全涉及 Docker/seccomp，本期不做。

→ **本期（Task 007）聚焦 #1 + #2 一起做**，它们互相独立又能放大彼此价值（有记忆的检索 = 会学习的研究助手）。

---

## 三、Task 007 目标（本期范围）

> **主题：给 Course Agent 装上「记忆」和「真实眼睛」**

### 3.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ 会话持久化（刷新不丢） | ❌ 多用户权限系统 |
| ✅ 短期记忆：滑动窗口 + 自动摘要压缩 | ❌ 复杂的 memory graph / 实体关系 |
| ✅ 长期记忆：Chroma 向量检索 | ❌ 全文检索引擎（Elasticsearch） |
| ✅ Memory 工具化（Agent 可主动 `recall` / `remember`） | ❌ 跨用户共享记忆 |
| ✅ 真实 `web_search`：DuckDuckGo（无 Key）+ Tavily（可选 Key） | ❌ 爬虫、登录后网页抓取 |
| ✅ 网页正文抽取（trafilatura / readability） | ❌ PDF/JS 渲染、图片 OCR（归到 Task 008） |

### 3.2 成功指标

1. [ ] 刷新浏览器，**历史对话仍在**
2. [ ] 连续对话 30+ 轮不爆 token（短期摘要生效）
3. [ ] 用户上一次说过的偏好（如"我喜欢用 Python"）在**新会话**里仍被记住（长期向量检索生效）
4. [ ] 输入"搜一下 transformer 论文"能返回**真实网页**结果（而不是 mock 字符串）
5. [ ] Agent 能在工具调用中显式执行 `recall("上次我们聊到什么")` → 返回相关历史片段
6. [ ] 所有新代码有单元测试，`pytest` 和 `ruff` 全绿
7. [ ] 完全向后兼容：旧的 CLI / Mock 流程不受影响

---

## 四、技术方案

### 4.1 Memory 子系统架构

```
┌──────────────── MemoryManager ────────────────┐
│                                                │
│   ┌─────────────┐    ┌─────────────────┐      │
│   │ ShortTerm   │    │ LongTerm         │      │
│   │ Memory      │    │ Memory           │      │
│   │             │    │                   │      │
│   │ 滑动窗口    │    │ Chroma 向量库    │      │
│   │ +           │    │ (SQLite backend) │      │
│   │ LLM 摘要    │    │                   │      │
│   └─────────────┘    └─────────────────┘      │
│        ▲                     ▲                 │
│        │ 追加/读取             │ 相似度检索     │
└────────┼─────────────────────┼─────────────────┘
         │                     │
    ┌────┴─────────────────────┴────┐
    │         AgentLoop              │
    │   每轮 user_input 前：         │
    │     - recall(relevant)         │
    │     - inject into context      │
    │   每轮 answer 后：             │
    │     - store(msg)               │
    └────────────────────────────────┘
```

### 4.2 模块设计

#### `course_agent/memory/base.py`

```python
class BaseMemory(Protocol):
    async def add(self, role: str, content: str, **meta: Any) -> None: ...
    async def recall(self, query: str, k: int = 5) -> list[MemoryRecord]: ...
    async def clear(self) -> None: ...
```

#### `course_agent/memory/short_term.py` — 滑动窗口 + 摘要压缩

```python
class ShortTermMemory(BaseMemory):
    """最近 N 条消息 + 超过阈值自动调用 LLM 压缩成摘要."""

    def __init__(self, llm: BaseLLM, max_turns: int = 20, compress_trigger: int = 16):
        ...

    async def compressed_history(self) -> list[LLMMessage]:
        """返回：[summary_msg?, ...最近若干条]"""
```

**压缩策略**：当 turn 数 > `compress_trigger`，把最早的一半轮次喂给 LLM 做 200 字摘要，替换为一条 `role=system` 的 `[PREVIOUS CONTEXT SUMMARY]` 消息。

#### `course_agent/memory/long_term.py` — Chroma 向量存储

```python
class LongTermMemory(BaseMemory):
    """基于 Chroma 的持久化向量记忆."""

    def __init__(self, persist_dir: str, embedder: BaseEmbedder):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("course_agent")

    async def add(self, role, content, **meta):
        emb = await self.embedder.embed(content)
        self.collection.add(
            ids=[str(uuid4())],
            embeddings=[emb],
            documents=[content],
            metadatas=[{"role": role, "ts": time.time(), **meta}],
        )
```

**Embedder 选择**：
- 首选 `BAAI/bge-small-zh-v1.5`（本地 sentence-transformers，免 Key、中文友好）
- 备选 `text-embedding-v3`（DashScope 兼容接口，远程）
- 抽象 `BaseEmbedder`，默认使用本地

#### `course_agent/memory/manager.py` — 统一入口

```python
class MemoryManager:
    def __init__(self, short: ShortTermMemory, long: LongTermMemory | None = None):
        ...

    async def enrich_context(self, user_input: str, base_history: list[LLMMessage]) -> list[LLMMessage]:
        """给 AgentLoop 用：注入 short-term + long-term 相关片段."""
        short = await self.short.compressed_history()
        if self.long:
            relevant = await self.long.recall(user_input, k=3)
            short.insert(0, LLMMessage(role="system", content=f"[RELEVANT MEMORIES]\n{relevant}"))
        return short + base_history
```

#### `course_agent/memory/tools.py` — 暴露为 Agent 工具

```python
@tool(name="recall", description="从长期记忆中检索与 query 相关的历史片段")
def recall(query: str, k: int = 3) -> str:
    ...

@tool(name="remember", description="主动把一条重要信息写入长期记忆（如用户偏好、关键结论）")
def remember(content: str, tag: str = "note") -> str:
    ...
```

### 4.3 Web 检索工具

#### `course_agent/tools/web_search_real.py`

```python
@tool(name="web_search", description="在互联网搜索并返回前 k 条结果（标题+摘要+URL）")
def web_search(query: str, k: int = 5) -> str:
    # 优先 Tavily（有 TAVILY_API_KEY），否则降级 DuckDuckGo HTML
    ...

@tool(name="web_fetch", description="抓取给定 URL 的网页正文（已去广告/导航）")
def web_fetch(url: str, max_chars: int = 4000) -> str:
    # requests + trafilatura
    ...
```

**策略**：
- `.env` 有 `TAVILY_API_KEY` → 用 Tavily（质量高、直接返回摘要）
- 没有 → 降级到 `duckduckgo_search`（无需 Key）
- `web_fetch` 用 `trafilatura` 提取正文，去掉导航/广告
- 所有网络调用：超时 10s、重试 2 次

### 4.4 Chainlit 侧改动

- 在 `chainlit_app.py` 的 `on_chat_start` 里：
  - 初始化 `MemoryManager`（`persist_dir=./data/memory/{user_id}`）
  - 把 `MemoryManager` 放进 `cl.user_session`
- 在 `on_message` 里：
  - 用 `manager.enrich_context(user_input, history)` 替代裸 history
  - Agent 返回后 `manager.add("user", ...)` + `manager.add("assistant", ...)`
- **开启 Chainlit data layer**（SQLite backend）→ 刷新不丢历史

---

## 五、实施步骤

### Step 1：依赖与骨架（0.5 天）
- [x] `pyproject.toml` 把 `chromadb>=0.5` 从 `[memory]` extra 提升为默认；新增 `ddgs`、`trafilatura`、`tiktoken`（`sentence-transformers` 改为可选 `[local-embed]`）
- [x] `course_agent/memory/` 下新建 `base.py` / `short_term.py` / `long_term.py` / `manager.py` / `embedders.py` / `tools.py` 骨架文件

### Step 2：短期记忆 + 摘要压缩（1 天）
- [x] `ShortTermMemory` 实现
- [x] 单测：验证超过阈值时触发压缩、压缩后 token 数显著下降（`tests/test_memory_short_term.py` 6 项全过）

### Step 3：长期记忆 + Chroma（1.5 天）
- [x] `BaseEmbedder` 抽象 + 离线 `HashEmbedder` + `OpenAIEmbedder`（DashScope/OpenAI 兼容）
- [x] `LongTermMemory` CRUD（基于 `chromadb.PersistentClient` + cosine HNSW）
- [x] `MemoryManager` 串联（`enrich_context` 注入 RELEVANT MEMORIES + 短期压缩历史）
- [x] 单测：add→recall 召回率验证（`tests/test_memory_long_term.py` 9 项 + `tests/test_memory_manager.py` 7 项全过）

### Step 4：Memory 工具化（0.5 天）
- [x] `recall` / `remember` 注册为 `@tool`（通过 `set_active_manager` 单例桥接 per-session manager）
- [x] 集成测试：`tests/test_memory_tools.py` 4 项 + 端到端跨实例脚本验证 score=0.52 召回成功

### Step 5：真实 Web 检索（1 天）
- [x] 用 `ddgs`（duckduckgo-search 的维护后继）替换 mock
- [x] 新增 `web_fetch` + trafilatura 正文抽取（HTML 标签剥离兜底）
- [x] 有 `TAVILY_API_KEY` 时优先走 Tavily，否则降级 DuckDuckGo
- [x] 所有网络调用加 10s 超时 + UA 伪装 + follow_redirects

### Step 6：Chainlit 接入 + 持久化（1 天）
- [x] `on_chat_start` 初始化 `MemoryManager` + `set_active_manager`
- [x] `on_message` 走 `enrich_context` + 回写双层记忆
- [x] Settings 面板新增 `启用长期记忆` Switch；场景切换只清短期，保留长期
- [x] 持久化目录 `data/memory/<session_id>/` + 加入 `.gitignore`

### Step 7：测试 + 文档（0.5 天）
- [x] 所有新代码的 pytest（54 passed + 5 skipped；`ruff check` clean）
- [x] README 新增「记忆系统」和「真实检索」章节（含工作流程图、Embedder 选择表、跨会话实测）
- [x] `task/task_007.md` 打钩标记完成项

**合计预估：6 天（全职），可根据实际进度调整。**

---

## 六、风险与应对

| 风险 | 应对 |
|---|---|
| Chroma 首次启动慢（下载 embedding 模型） | 启动时异步预热；README 提示 |
| `sentence-transformers` 包大（~500MB） | 作为可选依赖 `[memory-local]`；默认用远程 embedding |
| DuckDuckGo 被反爬 | 加 UA 伪装、超时 fallback 到返回空结果+提示用户配 Tavily |
| 记忆过多导致上下文膨胀 | `recall` 严格 top-k；摘要压缩兜底 |
| 持久化文件跨机器不兼容 | 记忆目录按 `data/memory/{user_id}` 隔离；提供 `course-agent memory clear` CLI |
| Python 3.13 下 chromadb 兼容性 | 提前跑一次 `pip install chromadb` 验证；已知 chromadb 0.5+ 支持 3.13 |

---

## 七、交付物清单

- [x] `course_agent/memory/base.py`
- [x] `course_agent/memory/short_term.py`
- [x] `course_agent/memory/long_term.py`
- [x] `course_agent/memory/manager.py`
- [x] `course_agent/memory/embedders.py`
- [x] `course_agent/memory/tools.py`
- [x] `course_agent/tools/web_tools.py`（覆盖旧 mock；同时承担 `web_search` 真实实现 + `web_fetch`，**比原计划合并为一个文件**）
- [x] `course_agent/ui/chainlit_app.py`（接入 MemoryManager + Switch）
- [x] `tests/test_memory_short_term.py`（6 项）
- [x] `tests/test_memory_long_term.py`（9 项）
- [x] `tests/test_memory_manager.py`（7 项）
- [x] `tests/test_memory_tools.py`（4 项）
- [x] `tests/test_web_tools.py`（4 项 + 2 项 RUN_LIVE_WEB gate）
- [x] `pyproject.toml` 更新依赖（chromadb / ddgs / trafilatura / tiktoken；`[local-embed]` 可选 extra）
- [x] `.env.example` 添加 `TAVILY_API_KEY`（可选）+ `EMBEDDING_MODEL` + `RUN_LIVE_WEB` 注释
- [x] `README.md` 添加「🧠 记忆系统」「🌐 真实 Web 检索」说明 + 项目结构 / Milestone / 工具表 / 对比表同步更新

---

## 八、后续可衔接的 Task

- **Task 008**：作业文件理解（`pdf_read` / `image_ocr`）
- **Task 009**：`python_exec` 沙箱执行（配合 Milestone 3 的 Executor Agent）
- **Task 010**：多 Agent 编排（Planner / Executor / Grader 三角色）
- **Task 011**：可观测性面板（token 统计 / 时延图 / 失败率）
- **Task 012**：生产化部署（Dockerfile + HTTPS）

---

## 九、完成后项目能力对比

| 能力 | Task 007 前 | Task 007 后 |
|---|---|---|
| 会话持久化 | ❌ 刷新丢失 | ✅ SQLite 持久化 |
| 长对话 token 控制 | ❌ 30 轮后爆 | ✅ 自动摘要压缩 |
| 跨会话记忆 | ❌ 无 | ✅ Chroma 向量召回 |
| 资料检索 | ❌ mock | ✅ DuckDuckGo + Tavily + 正文抽取 |
| 工具数量 | 4 个 | **7 个**（+ `recall` / `remember` / `web_fetch`） |
| 与普通 AI Chat 差距 | 中 | **明显拉开**：有记忆 + 能联网 |

---

> **一句话总结**：Task 007 做完，Course Agent 就从「一次性的聪明助手」升级为「会记得你、会去查资料的助教」，跟普通 Qwen/ChatGPT 网页版的差距会进一步拉开。
