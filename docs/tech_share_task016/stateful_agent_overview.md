# Task 016：Stateful Agent Overview

## 本期主题

Task 016 让项目从：

- graph-native agent platform

继续升级为：

- stateful agent platform

## 关键变化

- 引入 `TaskSession`
- 引入 `SessionStore`
- graph 支持 `wait_human_input` / `wait_approval`
- CLI 支持 `session list/show/resume/continue/cancel`
- Chainlit 可以展示 session id 与 waiting 状态

## 一句话总结

Task 015 讲“怎么把执行过程展示出来”，Task 016 讲“怎么把执行过程持续下去”。
