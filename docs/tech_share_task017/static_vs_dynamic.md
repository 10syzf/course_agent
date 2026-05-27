# Static Prefix vs Dynamic Tail

## `static_prefix`

- 面向全局共享规则
- 内容尽量稳定
- 适合作为 cache-friendly segment
- 典型内容：角色定义、安全红线、工具使用、Git 安全、输出风格

## `dynamic_tail`

- 面向当前请求实时编译
- 内容按环境和任务变化
- 典型内容：环境信息、`COURSE_AGENT.md`、memory notes、MCP notes、session notes、当前任务

## 为什么要拆层

- 让 prompt 有清晰边界
- 让多角色共享统一静态前缀
- 让任务态信息集中进入动态尾部
- 让 inspect / replay / profiling 更容易实现

## 当前项目里的落地方式

- `course_agent/prompt/static_prefix.py`
- `course_agent/prompt/dynamic_tail.py`
- `course_agent/prompt/compiler.py`

## 分享时可以强调

- 这不是“prompt 模板拆文件”
- 而是把稳定层和变化层显式化
- 后续做缓存、差异对比、benchmark 都有基础
