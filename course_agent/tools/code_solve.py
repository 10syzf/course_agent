"""自批改闭环工具：写代码 → 跑 → 失败就改 → 再跑（最多 N 轮）.

⚠️ 当前文件为 Task 009 Step 1 提交的**骨架**，完整实现见 Step 3。
   骨架阶段：
   - 已注册 `@tool` 到全局 Registry
   - 实际调用会返回 `[code_solve] (Task 009 Step 3 实现中) ...` 的占位提示
   - 不抛异常、不破坏现有 AgentLoop 行为

实现路线（Step 3 完成）：
  ① 拿到默认 LLM 句柄（factory.get_default_llm() 单例）
  ② for round in range(max_rounds):
       a. 让 LLM 写代码（system: 你是 Python 程序员，根据需求写代码 / 拿到上轮失败信息时只返回完整新代码）
       b. 拼接 code + "\n# === auto tests ===\n" + tests
       c. 调 python_exec(code, timeout=10)
       d. 解析 JSON：exit_code == 0 → 成功；否则把 stderr 截 1KB 喂回去
  ③ 返回 {success, rounds, code, last_error}
  ④ 硬上限 max_rounds=5；默认 3
"""

from __future__ import annotations

import json

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("code_solve")

_DEFAULT_MAX_ROUNDS = 3
_HARD_MAX_ROUNDS = 5


@tool(
    name="code_solve",
    description=(
        "自批改编程闭环：根据自然语言需求和断言测试，自动写 Python 代码、运行、"
        "失败时根据 stderr 自我修正、再运行，最多 N 轮。"
        "适合：学生让 Agent 帮写一个函数并要求自动验证。"
    ),
)
def code_solve(task: str, tests: str = "", max_rounds: int = 3) -> str:
    """自批改闭环工具骨架（Task 009 Step 1）.

    Args:
        task: 自然语言需求，如「写一个判断回文数的函数 is_palindrome(n)」。
        tests: 断言测试代码，会被追加到 LLM 写的代码末尾，如
            `assert is_palindrome(121) == True\\nassert is_palindrome(123) == False`。
        max_rounds: 最大自批改轮数，硬上限 5；默认 3。

    Returns:
        JSON 字符串：{success, rounds, code, last_error}。
    """
    rounds = max(1, min(int(max_rounds or _DEFAULT_MAX_ROUNDS), _HARD_MAX_ROUNDS))

    if not task or not task.strip():
        return json.dumps(
            {
                "success": False,
                "rounds": 0,
                "code": "",
                "last_error": "[code_solve] 入参 task 为空，请提供自然语言需求。",
            },
            ensure_ascii=False,
        )

    _log.warning(f"code_solve 骨架被调用 (Task 009 Step 3 尚未实现)：task={task[:40]!r}")

    return json.dumps(
        {
            "success": False,
            "rounds": 0,
            "code": "",
            "last_error": (
                f"[code_solve] (Task 009 Step 3 实现中) 已收到任务，max_rounds={rounds}，"
                f"tests 长度={len(tests)}。真实自批改循环将在 Step 3 接入。"
            ),
        },
        ensure_ascii=False,
    )
