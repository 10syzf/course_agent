"""工具系统：Registry + @tool 装饰器 + 内置工具."""
# ruff: noqa: I001, E402

# 必须先 import registry，因为下方所有内置/web/memory 工具的 @tool 装饰器都依赖它
from course_agent.tools.registry import Tool, ToolRegistry, get_registry, tool

from course_agent.tools import builtin  # noqa: F401  注册 calculator / file_read / file_write
from course_agent.tools import web_tools  # noqa: F401  注册真实 web_search / web_fetch
from course_agent.tools import python_exec as _python_exec  # noqa: F401  注册 python_exec
from course_agent.tools import pdf_tools as _pdf_tools  # noqa: F401  注册 pdf_read
from course_agent.tools import image_ocr as _image_ocr  # noqa: F401  注册 image_ocr (Task 009)
from course_agent.tools import code_solve as _code_solve  # noqa: F401  注册 code_solve (Task 009)
from course_agent.tools import mistake_book as _mistake_book  # noqa: F401  注册 add_mistake / list_mistakes / review_mistake (Task 010)
from course_agent.tools import kb as _kb  # noqa: F401  注册 kb_ingest / kb_search (Task 010)
from course_agent.memory import tools as _memory_tools  # noqa: F401  注册 recall / remember

__all__ = ["Tool", "ToolRegistry", "get_registry", "tool"]
