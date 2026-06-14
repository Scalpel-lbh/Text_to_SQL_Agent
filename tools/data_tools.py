"""
文件作用：
定义企业数据分析 Agent 可以调用的工具。

工具调用流程：
1. schema_search_tool 根据问题从 Chroma 检索相关数据库结构。
2. Agent 获取检索结果。
3. text_to_sql_tool 接收问题和检索结果，生成并执行 SQL。
"""

# json：将 Python 数据转换成 JSON 字符串，方便 Agent 读取
import json

# tool：将普通 Python 函数注册成 LangChain 工具
from langchain_core.tools import tool

# SchemaStore：负责 Chroma Schema 向量检索
from rag.schema_store import SchemaStore

# TextToSQLService：负责 SQL 生成、执行和自动修复
from services.text_to_sql_service import TextToSQLService


# 全局创建 SchemaStore，避免每次调用工具都重新加载 Chroma
schema_store = SchemaStore()

# 确保 Schema 文档已经写入 Chroma
schema_store.initialize()

# 创建 Text-to-SQL 服务
# Schema 检索已由 schema_search_tool 负责，因此不再注入 SchemaStore
text_to_sql_service = TextToSQLService()


@tool(
    description=(
        "从 Chroma 向量库检索与用户问题最相关的数据库表结构、字段含义、"
        "表关联关系和业务规则。处理业务数据查询前必须先调用本工具，"
        "然后将本工具返回的完整结果作为 schema_context 传给 "
        "text_to_sql_tool。"
    )
)
def schema_search_tool(query: str) -> str:
    """检索相关 Schema，并以结构化 JSON 返回结果。"""
    try:
        if not query.strip():
            return json.dumps(
                {
                    "success": False,
                    "query": query,
                    "matched_schemas": [],
                    "error_message": "查询内容不能为空",
                },
                ensure_ascii=False,
            )

        documents = schema_store.search(
            query=query,
            k=3,
        )

        if not documents:
            return json.dumps(
                {
                    "success": False,
                    "query": query,
                    "matched_schemas": [],
                    "error_message": "没有检索到相关数据库结构",
                },
                ensure_ascii=False,
            )

        matched_schemas = [
            {
                "table_name": document.metadata["table_name"],
                "retrieval_source": document.metadata.get(
                    "retrieval_source",
                    "unknown",
                ),
                "content": document.page_content,
            }
            for document in documents
        ]

        return json.dumps(
            {
                "success": True,
                "query": query,
                "matched_schemas": matched_schemas,
                "error_message": None,
            },
            ensure_ascii=False,
        )

    except Exception as error:
        # 工具不向外抛出异常，避免整个 Agent 请求变成 HTTP 500
        return json.dumps(
            {
                "success": False,
                "query": query,
                "matched_schemas": [],
                "error_message": str(error),
            },
            ensure_ascii=False,
        )


@tool(
    description=(
        "根据用户问题和 schema_search_tool 返回的数据库结构生成只读 SQL，"
        "执行查询并返回结果。调用本工具前必须先调用 schema_search_tool，"
        "schema_context 必须传入该工具返回的完整结果，禁止自行编造 Schema。"
    )
)
def text_to_sql_tool(
    question: str,
    schema_context: str,
) -> str:
    """执行 Text-to-SQL，并以结构化 JSON 返回结果。"""
    try:
        result = text_to_sql_service.run(
            question=question,
            schema_context=schema_context,
        )

        return json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )

    except Exception as error:
        return json.dumps(
            {
                "success": False,
                "question": question,
                "sql": None,
                "rows": [],
                "answer": "Text-to-SQL 工具执行失败。",
                "repaired": False,
                "error_message": str(error),
            },
            ensure_ascii=False,
        )