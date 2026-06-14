"""
文件作用：
    为企业数据分析 ReAct Agent 提供 FastAPI 接口。

主要功能：
    1. 提供健康检查接口。
    2. 接收 session_id 和当前问题。
    3. 从 Redis 读取多轮聊天历史。
    4. 调用 Agent 并保存本轮对话。
    5. 返回最终回答和工具调用轨迹。
    6. 提供会话历史清空接口。
"""


# FastAPI 用于创建 HTTP API 服务
from fastapi import FastAPI

# BaseModel 用于定义和校验请求、响应数据结构
# Field 用于为列表字段创建独立的默认空列表
from pydantic import BaseModel, Field

# DataAnalysisAgent 是企业数据分析 ReAct Agent
from agent.sql_agent import DataAnalysisAgent

# SessionService 负责 Redis 会话历史管理
from services.session_service import SessionService


# 创建 FastAPI 应用
app = FastAPI(
    title="Enterprise Data Analysis Agent API",
    version="1.0.0",
)

# 全局复用 Agent 和会话服务
agent = DataAnalysisAgent()
session_service = SessionService()


class QueryRequest(BaseModel):
    """数据分析请求体。"""

    session_id: str
    question: str


class QueryResponse(BaseModel):
    """数据分析响应体。"""

    session_id: str
    question: str
    answer: str
    tool_trace: list[dict] = Field(default_factory=list)


class ClearSessionRequest(BaseModel):
    """清空会话请求体。"""

    session_id: str


@app.get("/health")
def health() -> dict:
    """检查 API 服务是否正常运行。"""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """执行支持多轮上下文的数据分析查询。"""
    # 查询前，根据 session_id 读取历史记录
    history = session_service.get_history(req.session_id)

    # 将历史记录和当前问题传给 Agent
    result = agent.run(
        question=req.question,
        history=history,
    )

    # Agent 成功回答后，保存本轮问答
    session_service.save_turn(
        session_id=req.session_id,
        question=req.question,
        answer=result["answer"],
    )

    return QueryResponse(
        session_id=req.session_id,
        question=result["question"],
        answer=result["answer"],
        tool_trace=result["tool_trace"],
    )


@app.post("/session/clear")
def clear_session(req: ClearSessionRequest) -> dict:
    """清空指定 session_id 对应的聊天历史。"""
    session_service.clear_history(req.session_id)

    return {
        "status": "cleared",
        "session_id": req.session_id,
    }