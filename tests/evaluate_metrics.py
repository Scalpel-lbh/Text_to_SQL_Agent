"""
文件作用：
评估 Text-to-SQL ReAct Agent 的端到端效果。

评估指标：
1. Schema 必要表召回率：schema_search_tool 返回的表是否覆盖人工标注的 required_tables。
2. Text-to-SQL 执行成功率：text_to_sql_tool 是否返回 success=true。
3. 端到端响应延迟：从请求 /query 到拿到最终响应的总耗时。

运行前要求：
1. Docker Compose 已启动 API 和 Redis。
2. http://127.0.0.1:8000/health 返回 {"status": "ok"}。
"""

# json：负责请求体、响应体和评估报告的 JSON 编解码
import json

# re：用于从工具调用轨迹中提取 table_name 和 success 字段
import re

# statistics：用于计算平均延迟
import statistics

# time：用于统计接口响应耗时
import time

# uuid：生成独立 session_id，避免测试之间互相污染 Redis 会话
import uuid

# Path：定位并写入评估报告文件
from pathlib import Path

# urllib.request：Python 内置 HTTP 请求模块，不需要额外安装 requests
from urllib import request

# urllib.error：捕获 HTTP 请求异常
from urllib.error import HTTPError


# FastAPI 服务地址
BASE_URL = "http://127.0.0.1:8000"

# 评估报告输出路径
REPORT_PATH = Path("tests") / "evaluation_report.json"


# 人工构造的小规模业务查询测试集
# required_tables 表示回答该问题理论上必须覆盖的数据库表
TEST_CASES = [
    {
        "question": "销售额最高的商品及其销售额是多少？",
        "required_tables": ["products", "order_items", "orders"],
    },
    {
        "question": "销量最高的商品是什么？",
        "required_tables": ["products", "order_items"],
    },
    {
        "question": "每个商品的销售额是多少？",
        "required_tables": ["products", "order_items", "orders"],
    },
    {
        "question": "已支付订单一共有多少个？",
        "required_tables": ["orders"],
    },
    {
        "question": "退款订单数量是多少？",
        "required_tables": ["orders"],
    },
    {
        "question": "每个城市有多少用户？",
        "required_tables": ["users"],
    },
    {
        "question": "哪个城市的用户最多？",
        "required_tables": ["users"],
    },
    {
        "question": "每个用户下了多少订单？",
        "required_tables": ["users", "orders"],
    },
    {
        "question": "每个用户的消费金额是多少？",
        "required_tables": ["users", "orders", "order_items", "products"],
    },
    {
        "question": "购买扫地机器人的用户有哪些？",
        "required_tables": ["users", "orders", "order_items", "products"],
    },
    {
        "question": "各商品类别的销售额是多少？",
        "required_tables": ["products", "order_items", "orders"],
    },
    {
        "question": "平均每个订单包含多少件商品？",
        "required_tables": ["orders", "order_items"],
    },
    {
        "question": "每个订单的商品数量是多少？",
        "required_tables": ["orders", "order_items"],
    },
    {
        "question": "单价最高的商品是什么？",
        "required_tables": ["products"],
    },
    {
        "question": "有哪些商品类别？",
        "required_tables": ["products"],
    },
    {
        "question": "每种订单状态分别有多少订单？",
        "required_tables": ["orders"],
    },
    {
        "question": "每个商品被购买了多少件？",
        "required_tables": ["products", "order_items"],
    },
    {
        "question": "最近注册的用户是谁？",
        "required_tables": ["users"],
    },
    {
        "question": "每个城市用户的消费金额是多少？",
        "required_tables": ["users", "orders", "order_items", "products"],
    },
    {
        "question": "已支付订单中每个商品的销量是多少？",
        "required_tables": ["products", "order_items", "orders"],
    },
]


def post_json(path: str, body: dict) -> dict:
    """发送 POST 请求并返回 JSON 响应。"""
    request_body = json.dumps(body).encode("utf-8")

    http_request = request.Request(
        url=f"{BASE_URL}{path}",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        error_content = error.read().decode("utf-8")
        raise RuntimeError(
            f"接口请求失败，状态码：{error.code}，响应：{error_content}"
        ) from error


def get_json(path: str) -> dict:
    """发送 GET 请求并返回 JSON 响应。"""
    with request.urlopen(f"{BASE_URL}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def clear_session(session_id: str) -> None:
    """清空指定测试会话，避免历史上下文影响评估。"""
    post_json(
        "/session/clear",
        {"session_id": session_id},
    )


def find_trace_item(response_data: dict, tool_name: str) -> dict | None:
    """从工具轨迹中找到指定工具的调用记录。"""
    for trace_item in response_data.get("tool_trace", []):
        if trace_item.get("name") == tool_name:
            return trace_item

    return None


def extract_schema_tables(schema_trace: dict | None) -> set[str]:
    """从 schema_search_tool 的结果摘要中提取表名。"""
    if not schema_trace:
        return set()

    result_preview = schema_trace.get("result_preview", "")

    return set(
        re.findall(
            r'"table_name"\s*:\s*"([^"]+)"',
            result_preview,
        )
    )


def extract_sql_success(sql_trace: dict | None) -> bool:
    """判断 text_to_sql_tool 是否执行成功。"""
    if not sql_trace:
        return False

    if sql_trace.get("status") != "success":
        return False

    result_preview = sql_trace.get("result_preview", "")

    return '"success": true' in result_preview.lower()


def percentile(values: list[float], ratio: float) -> float:
    """计算简单百分位数。"""
    if not values:
        return 0.0

    sorted_values = sorted(values)
    index = int(round((len(sorted_values) - 1) * ratio))

    return sorted_values[index]


def evaluate() -> dict:
    """执行完整评估并返回统计结果。"""
    health_result = get_json("/health")

    if health_result.get("status") != "ok":
        raise RuntimeError("API 健康检查失败")

    case_results = []

    for index, case in enumerate(TEST_CASES, start=1):
        session_id = f"eval_{uuid.uuid4().hex}"
        clear_session(session_id)

        start_time = time.perf_counter()

        response_data = post_json(
            "/query",
            {
                "session_id": session_id,
                "question": case["question"],
            },
        )

        latency_seconds = time.perf_counter() - start_time

        schema_trace = find_trace_item(
            response_data,
            "schema_search_tool",
        )
        sql_trace = find_trace_item(
            response_data,
            "text_to_sql_tool",
        )

        retrieved_tables = extract_schema_tables(schema_trace)
        required_tables = set(case["required_tables"])

        schema_hit = required_tables.issubset(retrieved_tables)
        sql_success = extract_sql_success(sql_trace)

        case_result = {
            "index": index,
            "question": case["question"],
            "required_tables": sorted(required_tables),
            "retrieved_tables": sorted(retrieved_tables),
            "schema_hit": schema_hit,
            "sql_success": sql_success,
            "latency_seconds": round(latency_seconds, 3),
            "answer": response_data.get("answer", ""),
        }

        case_results.append(case_result)

        print(
            f"[{index:02d}/{len(TEST_CASES)}] "
            f"Schema命中={schema_hit} | "
            f"SQL成功={sql_success} | "
            f"耗时={latency_seconds:.2f}s | "
            f"问题={case['question']}"
        )

    schema_hits = [case["schema_hit"] for case in case_results]
    sql_successes = [case["sql_success"] for case in case_results]
    latencies = [case["latency_seconds"] for case in case_results]

    summary = {
        "total_cases": len(case_results),
        "schema_required_table_recall": round(
            sum(schema_hits) / len(schema_hits),
            4,
        ),
        "text_to_sql_success_rate": round(
            sum(sql_successes) / len(sql_successes),
            4,
        ),
        "average_latency_seconds": round(
            statistics.mean(latencies),
            3,
        ),
        "p95_latency_seconds": round(
            percentile(latencies, 0.95),
            3,
        ),
    }

    report = {
        "summary": summary,
        "case_results": case_results,
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


if __name__ == "__main__":
    evaluation_report = evaluate()

    print("\n评估汇总：")
    print(
        json.dumps(
            evaluation_report["summary"],
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\n详细报告已写入：{REPORT_PATH}")
