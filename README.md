# 企业数据分析 Text-to-SQL Agent

基于 LangChain、FastAPI、Chroma、Redis 和 Docker 构建的企业数据分析 Agent。用户可以通过自然语言查询电商数据库，系统自动检索相关 Schema、生成并执行只读 SQL，最后返回自然语言分析结果。

## 核心功能

- 基于 ReAct Agent 实现工具选择与调用
- 使用 Chroma 完成数据库 Schema RAG
- 根据表关联关系自动补充检索遗漏的关联表
- 使用大模型将自然语言转换为 SQLite SQL
- SQL 执行失败后自动修复一次
- SQL Guard 拦截危险语句和多语句执行
- 使用 Redis 保存多轮会话历史
- 提供 FastAPI 接口和 Swagger 文档
- 记录工具调用轨迹
- 使用 Docker Compose 一键部署 API 和 Redis

## 系统流程

```text
用户问题
    ↓
FastAPI 接收请求
    ↓
Redis 读取会话历史
    ↓
ReAct Agent
    ↓
schema_search_tool
    ↓
Chroma 检索相关 Schema
    ↓
关联表扩展
    ↓
text_to_sql_tool
    ↓
生成 SQL → SQL Guard → 执行 SQL
                      ↓
                 失败自动修复
    ↓
自然语言回答
    ↓
Redis 保存本轮会话