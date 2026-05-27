# Graph vs Legacy

## Legacy ReAct

- 优点：简单、稳定、容易理解
- 缺点：循环是隐式的，trace / replay / compare 能力弱

## Graph-native ReAct

- 优点：节点、边、条件跳转都显式可见
- 优点：天然适合 replay / benchmark / graph export
- 优点：更容易接 HITL / checkpoint / inspect
- 代价：运行时结构更复杂，trace 条目更多

## Task 015 的结论

Task 015 没有删除 legacy，而是保留双实现：

- `legacy`：适合作为稳定基线
- `langgraph`：适合作为平台化演进主方向
