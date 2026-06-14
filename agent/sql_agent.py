"""
文件作用：
    创建企业数据分析 ReAct Agent，并记录工具调用轨迹。

主要功能：
    1. 根据用户问题自主选择工具。
    2. 调用 schema_search_tool 或 text_to_sql_tool。
    3. 提取工具名称、参数、状态和结果摘要。
    4. 返回最终回答和工具调用轨迹。
"""


# Path 用于定位外部 Prompt 文件
from pathlib import Path

# create_agent 用于创建具备工具调用能力的 LangChain Agent
from langchain.agents import create_agent

# AIMessage 表示模型消息，可从中读取模型发起的 tool_calls
# ToolMessage 表示工具执行后返回给模型的消息
from langchain_core.messages import AIMessage, ToolMessage

# create_chat_model 用于创建大模型对象
from model.factory import create_chat_model

# 导入企业数据分析 Agent 可使用的两个工具
from tools.data_tools import schema_search_tool, text_to_sql_tool


# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 系统 Prompt 文件路径
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.txt"


class DataAnalysisAgent:
    """企业数据分析 ReAct Agent。"""

    def __init__(self) -> None:
        # 创建大模型对象
        self.llm = create_chat_model()

        # 创建 ReAct Agent，并注册数据库结构查询和数据查询工具
        self.agent = create_agent(
            model=self.llm,
            system_prompt=SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"),
            tools=[
                schema_search_tool,
                text_to_sql_tool,
            ],
        )

    def extract_tool_trace(self, messages: list) -> list[dict]:
        """从 Agent 消息列表中提取工具调用轨迹。"""
        tool_trace = []

        for message in messages:
            # AIMessage 中的 tool_calls 表示模型请求调用工具
            if isinstance(message, AIMessage):
                for tool_call in message.tool_calls:
                    tool_trace.append({
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["name"],
                        "args": tool_call["args"],
                        "status": "requested",
                        "result_preview": "",
                    })

            # ToolMessage 表示工具已经执行并返回结果
            if isinstance(message, ToolMessage):
                tool_call_id = message.tool_call_id

                # 根据 tool_call_id 找到对应的工具调用记录
                for trace_item in reversed(tool_trace):
                    if trace_item["tool_call_id"] == tool_call_id:
                        trace_item["status"] = getattr(
                            message,
                            "status",
                            "success",
                        )

                        # 只保留前 300 个字符，避免轨迹内容过长
                        trace_item["result_preview"] = str(
                            message.content
                        )[:2000]
                        break

        return tool_trace

    def run(self, question: str,history:list[dict]) -> dict:
        """
        执行企业数据分析 Agent。

        参数：
            question：用户当前提出的问题。
            history：从 Redis 读取的历史消息；首次对话时可以为空。

        返回：
            当前问题、最终回答和工具调用轨迹。
        """
        # 首次对话没有历史记录时，使用空列表
        history_messages = history or []

        messages = history_messages + [{
            "role":"user",
            "content":question
        }]
        result = self.agent.invoke({
            "messages": messages
        })

        messages = result["messages"]

        return {
            "question": question,
            "answer": messages[-1].content,
            "tool_trace": self.extract_tool_trace(messages),
        }


if __name__ == "__main__":
    agent = DataAnalysisAgent()

    history = [
        {
            "role": "user",
            "content": "销售额最高的商品是什么？",
        },
        {
            "role": "assistant",
            "content": "销售额最高的商品是扫地机器人。",
        },
    ]

    result = agent.run(
        question="那它的销售额是多少？",
        history=history,
    )

    print("最终回答：")
    print(result["answer"])

    print("\n工具调用轨迹：")
    for trace_item in result["tool_trace"]:
        print(trace_item)