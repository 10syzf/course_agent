# Task 003：接入真实 LLM（阿里云百炼 / OpenAI 兼容）

> 对应方案 A：将项目中的 `OpenAILLM` 占位实现替换为基于 `openai` SDK 的真实实现，支持 tool-calling，让 Agent Loop 能驱动真正的 Qwen 模型完成作业辅助。

## 一、目标与验收

### 1.1 核心目标
- 项目可在真实 Qwen 模型（通过百炼 OpenAI 兼容接口）下完成完整 ReAct 循环。
- 不破坏现有 `MockLLM` 链路，测试仍可离线运行。
- `uv run course-agent chat "..."` 使用真实模型跑通端到端流程。

### 1.2 验收标准
1. [ ] `uv run pytest` 全绿（包括离线测试，不依赖网络 / key）。
2. [ ] `uv run course-agent chat "帮我算 (3+5)*2"` 使用 `qwen-plus` 真实调用成功，并通过 `tool_call` 调用 `calculator`。
3. [ ] `uv run course-agent chat "帮我搜索一下 Transformer 架构"` 能触发 `web_search` 工具。
4. [ ] API Key 错误 / 网络异常时，Agent Loop 不会崩溃，能优雅返回错误信息。
5. [ ] 达到 429 限流时能自动退避重试（最多 2 次）。

---

## 二、技术方案

### 2.1 使用的 SDK
- 库：`openai>=1.30`
- 接入方式：OpenAI 官方 Python SDK，通过 `base_url` 指向百炼兼容接口。
- 兼容对象：DeepSeek / Qwen / 豆包等所有 OpenAI 兼容服务。

### 2.2 接口映射

| 项目抽象 | OpenAI SDK 对应物 |
| --- | --- |
| `BaseLLM.chat(messages, tools)` | `client.chat.completions.create(model, messages, tools, tool_choice="auto")` |
| `LLMMessage` → dict | `LLMMessage.to_openai()` 已有实现 |
| `ToolCall` ← response | `resp.choices[0].message.tool_calls[i].function.{name, arguments}` |
| `LLMResponse.content` | `resp.choices[0].message.content` |
| `LLMResponse.finish_reason` | `resp.choices[0].finish_reason` |

### 2.3 关键实现细节
- `arguments` 字段是 JSON 字符串，需 `json.loads` 成 dict 再塞进 `ToolCall`。
- Qwen 部分模型对 `tool_choice` 必须显式传 `"auto"` 才会触发工具调用。
- `temperature / max_tokens` 从 `LLMConfig` 读取；`**kwargs` 可覆盖。
- 首次请求前做一个轻量"存在性校验"（lazy-init `OpenAI` client）。

### 2.4 错误处理与重试
- `openai.AuthenticationError` → 直接抛出，提示 key 无效。
- `openai.RateLimitError` / HTTP 429 → 指数退避重试 2 次（1s, 3s）。
- `openai.APITimeoutError` / 网络异常 → 重试 1 次后抛出。
- 其他未知异常 → 包装成 `LLMResponse(content="[LLM 调用失败] ...", finish_reason="error")`，让 Agent Loop 优雅终止。

### 2.5 依赖变更
- `pyproject.toml`：将 `openai` 从 `[project.optional-dependencies].openai` 移到 `[project].dependencies`。
- 新增 `tenacity` 作为轻量重试库（可选；也可手写循环避免新依赖）。**决定：手写重试，不引入新依赖。**

---

## 三、实施步骤（开发顺序）

### Step 1：依赖调整
- [ ] 修改 `pyproject.toml`，将 `openai` 提升为默认依赖。
- [ ] 运行 `uv sync` 确认安装成功。

### Step 2：真实 `OpenAILLM` 实现
- [ ] 重写 `course_agent/llm/openai_like.py`：
  - [ ] 构造函数中懒加载 `OpenAI(base_url=..., api_key=...)`。
  - [ ] 实现 `chat()`：
    - 将 `list[LLMMessage]` 转为 OpenAI 消息格式。
    - 透传 `tools` schema，`tool_choice="auto"`。
    - 解析响应为 `LLMResponse`，包含 `content / tool_calls / finish_reason / raw`。
  - [ ] 添加 `_with_retry()` 辅助函数，处理 429/超时。
  - [ ] 对 `AuthenticationError` 提供友好报错（提示检查 key / base_url）。

### Step 3：工厂适配
- [ ] `course_agent/llm/factory.py` 保持不变（已按 provider 分派）。
- [ ] 验证 `create_llm()` 在 `provider=openai` 时走真实分支。

### Step 4：配置样例
- [ ] 保持 `.env.example` 为当前的百炼配置（key 已填）。
- [ ] `config/default.yaml` 的默认 provider 保持 `mock`（CI/离线友好）。
- [ ] README 中新增"接入真实 LLM"使用说明。

### Step 5：测试
- [ ] **离线单测（必跑）**：
  - [ ] `tests/test_openai_like_parse.py`：Mock 一个 `openai` client，验证响应解析逻辑正确（content / tool_calls / arguments 反序列化）。
- [ ] **在线集成测试（可选，有 key 才跑）**：
  - [ ] `tests/test_openai_live.py`：用环境变量 `RUN_LIVE_LLM=1` 作为开关，调用 `qwen-plus` 做一次最小对话和一次工具调用。
  - [ ] 默认 `@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM") != "1", reason="需要真实 key")`。

### Step 6：CLI 验证
- [ ] `uv run course-agent chat "帮我算一下 (12+8)*5 等于多少" --trace` 使用 qwen 成功。
- [ ] `uv run course-agent chat "帮我搜索 Transformer 架构" --trace` 成功。
- [ ] `uv run course-agent chat "给我讲讲牛顿第二定律"` 能直接给出答案（无工具调用）。

### Step 7：lint & 测试
- [ ] `uv run ruff check course_agent tests` 全绿。
- [ ] `uv run pytest` 全绿。

---

## 四、风险与应对

| 风险 | 应对 |
| --- | --- |
| Qwen 对 OpenAI tool_calling 行为微有差异（arguments 格式异常） | 解析时用 `json.loads` + fallback to `{}`，并记录 warning |
| 用户 key 无权限调用 `qwen-plus` | CLI 报错时明确提示可改为 `qwen-turbo` |
| 网络不通 / 配额耗尽 | 指数退避重试 + 优雅错误返回，不让 Agent Loop 挂死 |
| 真实调用成本 / 费用 | 默认 provider 仍为 mock，仅在用户显式切换到 openai 时走真实调用 |
| Tool schema 里带 default 值导致部分模型困惑 | 测试若失败，去掉 schema 中的 default 字段 |

---

## 五、交付物清单

- [ ] `course_agent/llm/openai_like.py` —— 真实实现
- [ ] `pyproject.toml` —— 依赖更新
- [ ] `tests/test_openai_like_parse.py` —— 离线解析测试
- [ ] `tests/test_openai_live.py` —— 可选在线测试
- [ ] `README.md` —— 新增"接入真实 LLM"章节
- [ ] 一次真实 `course-agent chat` 成功运行的截图/日志

---

## 六、预计工作量
- 代码实现：1 个小迭代（约 5~8 次编辑）
- 测试编写：2~3 个测试文件
- 验证联调：1 次真实调用即可判定成功

---

> 完成本 task 后，Agent Loop 将真正具备"理解自然语言 + 智能决策调用工具"的能力，为 Milestone 2（记忆系统）打下基础。
