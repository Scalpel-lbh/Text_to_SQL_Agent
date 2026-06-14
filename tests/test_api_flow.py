"""
文件作用：
对 FastAPI、Redis、多轮对话和 ReAct 工具链进行端到端测试。

运行前要求：
1. Docker Desktop 和 Redis 已启动。
2. FastAPI 已通过 uvicorn api.main:app --reload 启动。
"""


# json：负责请求体和响应体的 JSON 转换
import json

# urllib.request：Python 自带的 HTTP 请求模块，不需要额外安装 requests
from urllib import request

# urllib.error：捕获 HTTP 请求失败异常
from urllib.error import HTTPError


# FastAPI 服务地址
BASE_URL = "http://127.0.0.1:8000"

# 本次测试使用独立会话，避免旧聊天记录干扰
SESSION_ID = "api_test_001"


def get_json(path: str) -> dict:
    """发送 GET 请求并解析 JSON 响应。"""
    with request.urlopen(f"{BASE_URL}{path}") as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, body: dict) -> dict:
    """发送 POST 请求并解析 JSON 响应。"""
    request_body = json.dumps(body).encode("utf-8")

    http_request = request.Request(
        url=f"{BASE_URL}{path}",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request) as response:
            return json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        error_content = error.read().decode("utf-8")
        raise RuntimeError(
            f"接口请求失败，状态码：{error.code}，响应：{error_content}"
        ) from error


def assert_tool_chain(response_data: dict) -> None:
    """检查 Agent 是否按顺序调用两个工具。"""
    tool_names = [
        item["name"]
        for item in response_data["tool_trace"]
    ]

    assert "schema_search_tool" in tool_names, (
        "没有调用 schema_search_tool"
    )

    assert "text_to_sql_tool" in tool_names, (
        "没有调用 text_to_sql_tool"
    )

    schema_index = tool_names.index("schema_search_tool")
    sql_index = tool_names.index("text_to_sql_tool")

    assert schema_index < sql_index, (
        "工具顺序错误，必须先检索 Schema，再执行 Text-to-SQL"
    )


def main() -> None:
    """依次测试健康检查、清空会话、单轮查询和多轮指代。"""
    print("1. 测试健康检查")
    health_result = get_json("/health")

    assert health_result["status"] == "ok"
    print("健康检查通过")

    print("\n2. 清空测试会话")
    clear_result = post_json(
        "/session/clear",
        {"session_id": SESSION_ID},
    )

    assert clear_result["status"] == "cleared"
    print("会话清空成功")

    print("\n3. 测试第一轮数据查询")
    first_result = post_json(
        "/query",
        {
            "session_id": SESSION_ID,
            "question": "销售额最高的商品是什么？",
        },
    )

    assert_tool_chain(first_result)

    print("第一轮回答：")
    print(first_result["answer"])
    print("工具链检查通过")

    print("\n4. 测试多轮指代查询")
    second_result = post_json(
        "/query",
        {
            "session_id": SESSION_ID,
            "question": "那它属于什么商品类别？",
        },
    )

    print("第二轮回答：")
    print(second_result["answer"])
    print("第二轮工具轨迹：")
    print(second_result["tool_trace"])

    assert_tool_chain(second_result)

    print("多轮查询检查通过")


if __name__ == "__main__":
    main()