# Task 010：让 Agent「记得住错」+「翻得到书」—— 错题本 / 间隔复习 / 教材 RAG

> 本 Task 基于 Task 009（image_ocr 多模态 + code_solve 自批改 + python_exec 装包白名单 + doctor 8 项）完成后的项目现状，规划下一阶段最值得开发的方向。
>
> **核心命题**：Task 008 给了 Agent「手」，Task 009 给了 Agent「眼」+「自我反思」，但 Agent **每次会话都是失忆开局**——学生上一次错在哪里、教材里第几页讲过这个知识点，Agent **完全无感**。`course_agent` 这个名字承诺的是「**陪学**」，而陪学的核心是**记住学生**和**用得上教材**。Task 010 要补这两块——让 Agent 真正配得上「课程助手」这个定位。

---

## 一、当前项目现状盘点（Task 009 收尾后）

### 1.1 已具备的能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 + 异步 + 回调 |
| LLM 抽象层 | ✅ | 文本：OpenAI 兼容；**多模态：`get_default_llm()` + 直接 OpenAI SDK 多模态消息** |
| Tool Registry | ✅ | `@tool` + JSON Schema |
| **11 个工具** | ✅ | calculator / file_read / file_write / web_search / web_fetch / **python_exec（含 6 包白名单）** / **pdf_read（含 OCR 兜底）** / **image_ocr** / **code_solve（自批改 ≤3 轮）** / recall / remember |
| Memory 子系统 | ✅ | 短期滑窗 + LLM 摘要 + Chroma 长期向量库 + HashEmbedder 离线兜底 |
| Web 检索 | ✅ | Tavily / DuckDuckGo + trafilatura |
| Chainlit Web UI | ✅ | per-session + Settings + 场景按钮 + **图片拖拽上传** |
| CLI | ✅ | `chat` / `tools` / `version` / `ui` / `doctor`（**8 项**） |
| 错误分类 | ✅ | 6 类（Task 008 已固化） |
| 测试 + Lint | ✅ | **125 passed + 6 skipped**；ruff clean |

### 1.2 当前明显的缺口

| 缺口 | 当前状态 | 痛点 |
|---|---|---|
| **错题不留痕** | ❌ Memory 是「相似度检索」，不是「错题分类账」 | 学生今天问「什么是动态规划」错了，明天再问类似题，Agent 不会「特别警惕」也不会主动回顾——失去了陪学的核心价值 |
| **教材读完即扔** | ⚠️ `pdf_read` 一次性返回文本，没有沉淀到向量库 | 大教材一来就爆 context；学生下次问「书里第几章讲过 RSA」Agent 答不出 |
| **没有主动学习提示** | ❌ Chainlit 启动只是空白会话 | Agent 永远被动；陪学场景应该「老师主动追问昨天的错题」 |
| **流式输出**（Task 009 已识别，仍未做） | ⚠️ `arun` 等 LLM 整个 response 才 yield | 长答案"卡几秒突然出现"，体验不顺畅 |
| **多 Agent 编排** | ❌ `agent/` `orchestrator/` 仍空 | Task 009 解锁了「出题人 / 解题人 / 批改人」三角分工的素材，但还没编排 |
| **可观测面板** | ⚠️ 只有 loguru | UI 看不到 token 消耗 / 工具失败率 |
| **会话持久化** | ❌ Chainlit data layer 未开 | 关浏览器丢消息原文 |

### 1.3 Task 009 实战教训沉淀

| 教训 | 已修复 | 仍需注意 |
|---|---|---|
| `_TINY_PNG_B64` 1×1 探活被 Qwen-VL 拒收 | ✅ 改为 stdlib 现场合成 64×64 灰度 PNG | 「OpenAI 兼容」≠ 所有边界条件兼容；新加 VL 服务时要先做 happy path 探活 |
| `python -I` 与 `PYTHONPATH` 冲突 | ✅ 用 `extra_packages` 时摘 `-I` | 沙箱安全选项之间互相打架是常见陷阱；新增任何 sandbox flag 前先评估副作用 |
| `_extract_image_paths()` 只读 `cl.Image` | ✅ 已实现 | 后续若支持 PDF 拖拽 / 音频上传，要扩展同名 helper（不要新加函数） |
| `code_solve` stderr 反馈 1 KB 上限 | ✅ 已实现 | 部分长 traceback 会被截尾——可后续做「智能摘要」而不是简单截断 |
| 错题相关概念 Memory 检索召回率不稳 | ⚠️ HashEmbedder 仅 hash bag-of-words；中文短句相似度差 | Task 010 RAG 要正面解决「真 embedding 不可用时怎么办」的问题 |

---

## 二、候选开发方向（脑暴 + 打分）

10 个候选，按「价值 / 成本 / 与现有代码契合度」打分：

| # | 方向 | 价值 | 成本 | 契合度 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **错题本 `mistake_book`** + SM-2 间隔复习 | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | course_agent 之名、陪学之实的核心；复用 SQLite + 既有 11 个工具 |
| **2** | **教材 RAG**（`kb_ingest` + `kb_search`，复用 Chroma） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 复用已有 Chroma + pdf_read；让回答带「教材 P.42」引用，可信度暴涨 |
| **3** | **主动学习提示**（启动欢迎 + 待复习推送） | 🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 把 #1 落到 UI；几乎零新代码就能让 Agent「显得很主动」 |
| **4** | 真流式 streaming | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | UX 大杀器；但与 tool_call 拼装逻辑耦合，独立成 Task 011 更稳 |
| **5** | 多 Agent 编排（Planner → Solver → Grader） | 🔥🔥🔥🔥 | 高 | ⭐⭐⭐ | ⭐⭐⭐ | 价值大但体量也大；先把数据底座（错题本 + 教材库）建好再编排 |
| **6** | Chainlit data layer 持久化 | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 错题本一旦上线，data layer 是天然搭档；但相对独立可后置 |
| **7** | 可观测面板（token / 时延 / 失败率） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 调优用，对学生用户感知不强 |
| **8** | LaTeX 公式渲染 / Markdown 数学增强 | 🔥🔥🔥 | 低 | ⭐⭐⭐ | ⭐⭐⭐ | Task 009 image_ocr 抽出的公式现在显示成纯文本难看；Chainlit 内置 KaTeX 即可 |
| **9** | Dockerfile + docker-compose | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 推广必备但当前个人用户场景撑得住 `uv sync` |
| **10** | 题目生成器（基于错题本生成同类型新题） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 强依赖 #1；放到 Task 011/012 再做 |

### 2.1 挑选逻辑

- **#1 错题本** 是 `course_agent` 名字承诺的核心——没有它，这个项目只是「另一个 ChatGPT 套壳」。**必做**。
- **#2 教材 RAG** 是 #1 的天然搭档——错题本里记下「线性代数 第 4 章 P.83 没看懂」时，能直接 `kb_search("特征值分解")` 翻到原文，闭环立刻通。**必做**。
- **#3 主动提示** 是把 #1 + #2 落到用户面前的最后一公里——「每次打开 Chainlit，Agent 主动说『今天有 3 道错题待复习，要不要先看看？』」教学体验跃升。**必做**。
- **#4 流式** 价值高但和 tool_call 拼装强耦合，独立成 Task 011 更不容易出故障。
- **#5 多 Agent** 等数据底座（#1+#2）建好后再做，分工更清晰。
- **#10 题目生成器** 强依赖 #1，等 Task 011 做。

→ **本期（Task 010）聚焦**：#1 错题本 + 间隔复习 + #2 教材 RAG + #3 主动提示（最后一公里 UI 整合）

---

## 三、Task 010 目标（本期范围）

> **主题：从「会回答」到「会陪学」—— 学习闭环数据底座**

### 3.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ `add_mistake / list_mistakes / review_mistake` 三个工具，SQLite 持久化 | ❌ 跨设备同步 / 多用户隔离（先单机单用户） |
| ✅ SM-2 简化版间隔复习算法（quality 0-5 → 下次复习日期） | ❌ 复杂的 FSRS 算法 / Anki 兼容导入导出 |
| ✅ `kb_ingest(path_or_url) → kb_search(query, top_k)` 教材 RAG，复用现有 Chroma | ❌ 多模态 chunk（图片 / 表格按结构入库）；先纯文本 chunk |
| ✅ Chunking 策略：固定字符长度 + overlap（默认 800 / 100） | ❌ semantic chunker / 句法树切分（先朴素够用） |
| ✅ `kb_search` 返回结果带 `source` + `page` 两个字段，便于 LLM 引用 | ❌ rerank 模型 / 多路召回融合 |
| ✅ Chainlit 启动欢迎语：检测今日待复习数，主动提示 | ❌ 邮件 / 推送通知 |
| ✅ Chainlit `/mistakes` slash command 列出全部错题 | ❌ 独立 mistake-management 后台页面 |
| ✅ Chainlit 答题失败后自动追问「要不要记入错题本？」（Action 按钮） | ❌ 自动判错（学生说"对了"才算对，不强行 grader） |
| ✅ doctor 新增第 9 项：SQLite 错题库可读写 + Chroma kb collection 状态 | ❌ 错题库自动迁移 / 备份 |
| ✅ CLI 新增 `course-agent mistakes` 子命令（`list` / `review` / `due`） | ❌ TUI（先用纯文本表格） |
| ✅ 完全向后兼容：不开启错题本时，11 个工具行为完全不变 | — |

### 3.2 成功指标

1. [x] 学生答错一道题后，Agent 给出 `[记入错题本]` 按钮，点击后写入 SQLite，下一轮 `list_mistakes` 能查到
2. [x] 关掉浏览器、重开 Chainlit，欢迎语显示「📓 今天有 N 道错题待复习」（N>0 时显示，N=0 时正常打开）
3. [x] `kb_ingest("course_agent/data/sample_textbook.pdf")` 后，`kb_search("RSA 加密原理")` 能返回相关 chunk + 页码
4. [x] Agent 在回答时如果调了 `kb_search`，回答末尾自动出现「📚 参考：教材 P.42」字样（system prompt 引导）
5. [x] SM-2 复习曲线工作：quality=5 时 interval 翻倍；quality=0 时 interval 重置为 1
6. [x] `course-agent mistakes due` 在 CLI 列出今日待复习题目（与 Web UI 数据同源）
7. [x] `course-agent doctor` 第 9 项检查 SQLite + Chroma kb collection 都通
8. [x] HashEmbedder 兜底场景下 `kb_search` 不崩，但会在结果里附「⚠️ 当前用 hash 兜底，召回率有限」提示
9. [x] 全部新代码有单测，**pytest ≥ 145 passed**，ruff clean
10. [x] README 增加「📓 错题本 / 📚 教材库」两节用法

---

## 四、技术方案

### 4.1 错题本数据模型

**存储**：SQLite，路径 `~/.cache/course-agent/mistakes.db`（与现有 `~/.cache/course-agent/pkgs` 同根，便于 `course-agent doctor` 一并检查）

```sql
CREATE TABLE IF NOT EXISTS mistakes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    question     TEXT NOT NULL,                 -- 题目原文
    wrong_answer TEXT,                          -- 学生 / Agent 当时给的错答
    correct_answer TEXT,                        -- 正确答案 / 关键解析
    tags         TEXT,                          -- 逗号分隔，例如 "线代,特征值"
    source       TEXT,                          -- 来源：image_ocr 抽出 / PDF P.x / 手输
    created_at   TEXT NOT NULL,                 -- ISO8601
    -- SM-2 字段
    interval_days REAL NOT NULL DEFAULT 1.0,    -- 距离上次的间隔
    repetitions   INTEGER NOT NULL DEFAULT 0,   -- 连续答对次数
    easiness      REAL NOT NULL DEFAULT 2.5,    -- EF
    next_review_at TEXT NOT NULL                -- ISO8601 下次复习日期
);
CREATE INDEX IF NOT EXISTS idx_due ON mistakes(next_review_at);
CREATE INDEX IF NOT EXISTS idx_tags ON mistakes(tags);
```

**SM-2 简化算法**（参考 SuperMemo 2，做学生友好的 6 等级评价）：

```python
def update_sm2(easiness: float, interval: float, repetitions: int, quality: int):
    """quality: 0=完全不会, 1=想起来但错, 2=错但有印象, 3=磕巴对, 4=对, 5=秒答"""
    if quality < 3:
        repetitions = 0
        interval = 1.0
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1.0
        elif repetitions == 2:
            interval = 6.0
        else:
            interval = round(interval * easiness, 1)
    easiness = max(1.3, easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return easiness, interval, repetitions
```

### 4.2 错题本工具签名

```python
@tool(description="把一道做错的题目记入错题本")
def add_mistake(
    question: str,
    correct_answer: str,
    wrong_answer: str = "",
    tags: str = "",
    source: str = "",
) -> str: ...

@tool(description="列出错题，可按 tag 过滤或只看今日待复习")
def list_mistakes(tag: str = "", due_only: bool = False, limit: int = 20) -> str: ...

@tool(description="对一道错题打分（0-5），更新下次复习日期")
def review_mistake(mistake_id: int, quality: int) -> str: ...
```

### 4.3 教材 RAG（kb_ingest + kb_search）

**存储**：复用现有 Chroma persistent client，但用**独立 collection**：`kb_textbook`（与 Memory 的 `long_term` 完全隔离，避免污染）

**Chunking**：固定 800 字符 + 100 字符 overlap（中文友好；不按句号切，纯字符切片，简单可靠）

**入库流程**：
```
kb_ingest(path_or_url)
   │
   ├─→ 判别 path / url
   ├─→ 如果是 PDF → 复用 pdf_read 抽文本（含 Task 009 OCR 兜底！）
   ├─→ 如果是 .md / .txt → 直接读
   ├─→ 切 chunk（800/100）
   ├─→ embed → upsert 到 Chroma kb_textbook collection
   │     metadata: {source: 文件名, page: 页码（PDF 才有）, chunk_idx: 0..N}
   ├─→ 返回："已摄入 X 个 chunk，来源：xxx.pdf (Y 页)"
   └─→ 失败时降级：返回 "[kb_ingest] 解析失败：..."
```

**检索流程**：
```
kb_search(query, top_k=5)
   │
   ├─→ embed query
   ├─→ Chroma similarity_search → top_k chunks
   ├─→ 拼接结果（每段带 [📚 source P.page] 头）
   ├─→ HashEmbedder 兜底时在结尾追加 "⚠️ 当前 hash 兜底..."
   └─→ 返回字符串（≤ 8 KB）
```

### 4.4 主动学习提示（Chainlit 整合）

**`@cl.on_chat_start` 增强**（位于 [chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py)）：

```python
# 启动时查询今日待复习数
from course_agent.tools.mistake_book import _count_due_today
due = _count_due_today()
if due > 0:
    await cl.Message(
        content=f"📓 **今天有 {due} 道错题待复习**\n输入 `/mistakes` 查看，或直接说「开始复习」让我陪你过一遍。",
        author="System",
    ).send()
```

**`@cl.on_message` 失败追问**（在 `result` 出来后判断 `result.success` 或 LLM 显式说"我不确定"）：

```python
# 简化：检测 LLM 输出关键词或工具失败链
if _looks_like_mistake(message.content, result.answer):
    actions = [cl.Action(name="记入错题本", value="add_mistake", ...)]
    await cl.Message(content="要把这道题记入错题本吗？", actions=actions).send()
```

**`/mistakes` slash command**：Chainlit 1.x 没有官方 slash 概念，用 `cl.on_message` 内开头匹配 `/mistakes` 走分支即可。

### 4.5 doctor 第 9 项

```python
def _check_mistake_kb() -> tuple[str, str, str]:
    """检查 SQLite mistake.db 可读写 + Chroma kb_textbook collection 状态."""
    from course_agent.storage.mistake_db import get_db_path, ensure_schema
    from chromadb import PersistentClient
    
    db_path = get_db_path()
    try:
        ensure_schema()  # 幂等建表
        n_due = _count_due_today()
        # Chroma kb collection
        client = PersistentClient(path=str(db_path.parent / "chroma"))
        try:
            kb = client.get_collection("kb_textbook")
            kb_n = kb.count()
        except Exception:
            kb_n = 0
        return ("✅", f"mistakes.db OK", f"待复习 {n_due} 道；教材库 {kb_n} chunks")
    except Exception as e:
        return ("❌", type(e).__name__, str(e)[:160])
```

### 4.6 CLI `course-agent mistakes` 子命令

复用现有 typer：
```python
mistakes_app = typer.Typer(help="错题本管理")
app.add_typer(mistakes_app, name="mistakes")

@mistakes_app.command("list")
def cmd_list(tag: str = "", limit: int = 20): ...

@mistakes_app.command("due")
def cmd_due(): ...

@mistakes_app.command("review")
def cmd_review(mistake_id: int, quality: int): ...
```

---

## 五、Step-by-Step 实施计划

| Step | 内容 | 关键文件 | 依赖 |
|---|---|---|---|
| **1** | **依赖 + 骨架** | `pyproject.toml`（无新增三方包；用 stdlib `sqlite3`）；新建 `course_agent/storage/mistake_db.py`、`course_agent/tools/mistake_book.py`、`course_agent/tools/kb.py` 骨架（仅返回降级提示）；`course_agent/tools/__init__.py` 注册 4 个新工具（add_mistake / list_mistakes / review_mistake / kb_ingest 暂返回"未实现") | — |
| **2** | **错题本 SQLite 层** | `course_agent/storage/mistake_db.py`：`get_db_path()` / `ensure_schema()` / CRUD helpers / `update_sm2()` 算法 | Step 1 |
| **3** | **错题本工具实装** | `course_agent/tools/mistake_book.py`：`add_mistake / list_mistakes / review_mistake` 真实现；返回友好的 markdown 表格 | Step 2 |
| **4** | **教材 RAG 层** | `course_agent/tools/kb.py`：`_get_kb_collection()` 复用 Chroma 但独立 collection；`_chunk_text()` 800/100；`kb_ingest()` 调 `pdf_read` 或文件读；`kb_search()` 返回带 source+page 的拼接 | Step 1（不依赖错题本） |
| **5** | **CLI mistakes 子命令** | `course_agent/cli.py`：新增 `mistakes_app` typer；3 个子命令 | Step 3 |
| **6** | **doctor 第 9 项** | `course_agent/cli.py`：`_check_mistake_kb()`；插入到 doctor 流程 | Step 3 + Step 4 |
| **7** | **Chainlit 整合**（主动提示 + Action 按钮 + /mistakes） | `course_agent/ui/chainlit_app.py`：on_chat_start 欢迎语 + on_message 错题本 Action + /mistakes 分支 | Step 3 |
| **8** | **测试 + ruff + README + 勾选** | `tests/test_mistake_db.py`、`tests/test_mistake_book.py`、`tests/test_kb.py`、`tests/test_cli_mistakes.py`；README 新增 2 节；task_010.md 全勾 | 全部前置 |

---

## 六、测试矩阵

### 6.1 新增测试文件（≥ 20 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_mistake_db.py` | SM-2 算法各档 quality / schema 幂等 / 并发安全（多 connection） | ≥ 6 |
| `tests/test_mistake_book.py` | add/list/review 三工具的输入校验 / 友好降级 / 中文 tag | ≥ 5 |
| `tests/test_kb.py` | chunk 切分边界 / ingest PDF（mock pdf_read）/ 真 embedder 与 hash 兜底两条路径 / search 结果格式 | ≥ 5 |
| `tests/test_cli_mistakes.py` | typer subapp 路由 / list/due/review 三命令的退出码 + 输出 | ≥ 4 |

### 6.2 回归测试

- 不开启错题本（不 import mistake_book）的场景下，Task 008/009 全部 125 个用例继续通过
- `course-agent doctor` 第 1~8 项不受新增第 9 项影响

---

## 七、交付物 Checklist

### 代码
- [x] `course_agent/storage/mistake_db.py`（新文件，~150 行）
- [x] `course_agent/storage/__init__.py`（新文件，仅 re-export）
- [x] `course_agent/tools/mistake_book.py`（新文件，~120 行）
- [x] `course_agent/tools/kb.py`（新文件，~180 行）
- [x] `course_agent/tools/__init__.py`（注册 4 个新工具，**11 → 15** 个）
- [x] `course_agent/cli.py`（新增 `mistakes` subapp + doctor 第 9 项）
- [x] `course_agent/ui/chainlit_app.py`（on_chat_start 欢迎语 + Action 按钮 + /mistakes 分支）

### 测试 / 配置
- [x] `tests/test_mistake_db.py`、`tests/test_mistake_book.py`、`tests/test_kb.py`、`tests/test_cli_mistakes.py`
- [x] `pytest -q` 全绿（≥ 145 passed）
- [x] `ruff check .` 全绿

### 文档
- [x] `README.md` 新增「📓 错题本」「📚 教材库」两节
- [x] `README.md` 工具数表 11 → **15**；doctor 8 项 → **9 项**；测试数 125 → **≥ 145**
- [x] `README.md` 项目结构补 `storage/`、`tools/mistake_book.py`、`tools/kb.py`
- [x] `task/task_010.md`（本文）成功指标 10 项与交付物全勾

### 验证脚本（推荐手动跑一遍）
- [x] `course-agent doctor` → 9/9 ✅
- [x] `course-agent mistakes due` → CLI 输出今日待复习
- [x] Chainlit 上传一份 markdown 教材 → 调 `kb_ingest` → 后续问答带 `📚 参考：xxx`

---

## 八、教学性总结：为什么 Task 010 是「数据底座」而不是「酷炫功能」

Task 008 解决了「跑代码」，Task 009 解决了「看图 + 反思」，**这两个 Task 的共性是「让 Agent 在单次会话内更强**」。但 `course_agent` 这个项目的英文翻译是「**课程**助手」——课程的本质是**跨会话的连续学习**，而连续学习需要两个数据底座：

1. **学生侧的状态**（错过什么、什么时候该复习） → 错题本 + SM-2
2. **教材侧的状态**（哪一页讲过什么） → kb_ingest + kb_search

没有这两个底座，无论 Agent 单轮多聪明，**第二次见到学生时仍然是个陌生人**。Task 010 把这一点补齐，后续 Task 011/012 才能在此之上做：
- 「Planner Agent」根据**错题本分布**规划本周学习路径
- 「Examiner Agent」从**教材库**抽题、用错题本判难度
- 「Reviewer Agent」用**SM-2 排程**主动追问昨天的错题

> **一句话定位**：Task 010 是「Agent 智商」转「Agent 情商」的拐点——它让 Agent 从**回答机器**变成**陪伴者**。

---

## 九、风险与备选

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Chroma 独立 collection 与 Memory long_term 命名冲突 | 中 | Memory 长期记忆与教材 chunk 串味 | 用前缀隔离：`mem_long_term` vs `kb_textbook`，并在 doctor 列出 collection 列表 |
| 大教材 chunk 数过多（>10000）导致 ingest 卡住 | 中 | 用户体验差 | `kb_ingest` 加进度日志（每 100 chunk loguru.info）；超过 5000 chunk 时强制分批 |
| SM-2 quality 输入是 0-5，UI 上不直观 | 低 | 学生不会用 | Chainlit 用 5 个 emoji 按钮（😵/😣/🤔/😐/🙂/😎）映射到 0-5 |
| Chainlit Action 在我当前版本可能 API 改名 | 中 | UI 部分崩 | 实施时先 `cl.Action.__init__` 看一下当前签名再写 |
| HashEmbedder 用于 kb_search 召回率太差几乎不可用 | 高 | 体验差但不崩 | 在结果里**显著提示**「⚠️ 兜底模式，建议配置真 embedding」；不假装效果 |

---

## 十、显式不在本期范围（防 scope creep）

- ❌ 错题本跨设备同步 / 多用户隔离 / 云端备份
- ❌ 教材 RAG 的 rerank / hybrid search / multi-vector
- ❌ 题目自动生成器（基于错题本造同类型新题）→ Task 011
- ❌ 多 Agent 编排（Planner / Solver / Grader）→ Task 011/012
- ❌ 真流式 token-by-token 输出 → Task 011
- ❌ Anki 兼容导入导出
- ❌ FSRS 算法升级（SM-2 简化版够教育意义）
- ❌ 学习数据可视化（折线图 / 复习曲线）

> 上面这些是好东西，但**塞进 Task 010 会让本期失焦**。一次只解决一个数据底座问题——错题状态 + 教材状态——把它们做扎实，比同时做 5 件半成品有价值得多。
