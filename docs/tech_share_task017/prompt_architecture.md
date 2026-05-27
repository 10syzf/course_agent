# Task 017：Prompt Architecture

## 本期主题

Task 017 把项目从：

- stateful agent platform

继续升级为：

- prompt-native agent platform

## 关键变化

- 新增 `PromptSection` / `PromptEnvelope`
- 新增统一 `compile_prompt()` 入口
- 引入 `static_prefix` / `dynamic_tail` 两段式 prompt
- 支持 prompt artifact 落盘、latest 查看与 markdown 导出
- 支持 prompt profiling

## 适合分享时强调

- runtime 解决“怎么执行”
- session 解决“怎么恢复执行”
- prompt architecture 解决“模型到底看到了什么”

## 一句话总结

Task 017 不是单纯“多写一点提示词”，而是把 prompt 本身做成了可分层、可观察、可复用的基础设施。
