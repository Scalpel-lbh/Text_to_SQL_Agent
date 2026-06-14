"""
文件作用：
封装完整的 Text-to-SQL 业务流程。

主要流程：
1. 接收 schema_search_tool 检索出的相关表结构
2. 将相关 Schema 和用户问题交给大模型生成 SQL
3. 校验并执行 SQL
4. SQL 执行失败时，让大模型自动修复一次
5. 将查询结果整理成自然语言回答
"""

# json：将查询结果转换成 JSON 字符串，便于生成回答
import json

# Path：以跨平台方式定位 Prompt 文件
from pathlib import Path

# Any：表示字典中的值可以是任意类型
from typing import Any

# SQLAlchemyError：捕获 SQLAlchemy 执行 SQL 时产生的异常
from sqlalchemy.exc import SQLAlchemyError

# 数据库相关方法：执行 SQL
from database.db import execute_sql



# get_llm：创建项目使用的大语言模型
from model.factory import create_chat_model


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# SQL 生成 Prompt
SQL_PROMPT_PATH = BASE_DIR / "prompts" / "sql_prompt.txt"

# SQL 修复 Prompt
SQL_REPAIR_PROMPT_PATH = BASE_DIR / "prompts" / "sql_repair_prompt.txt"


class TextToSQLService:
    """负责完成从自然语言问题到数据库查询结果的整个流程。"""

    def __init__(self):
        # 初始化大语言模型
        self.llm = create_chat_model()

        # 读取 SQL 生成提示词
        self.sql_prompt_template = SQL_PROMPT_PATH.read_text(
            encoding="utf-8"
        )

        # 读取 SQL 修复提示词
        self.sql_repair_prompt_template = SQL_REPAIR_PROMPT_PATH.read_text(
            encoding="utf-8"
        )


    def build_sql_prompt(self, question: str, schema: str) -> str:
        """将相关 Schema 和用户问题填入 SQL 生成 Prompt。"""
        return self.sql_prompt_template.format(
            schema=schema,
            question=question,
        )

    def build_repair_prompt(
        self,
        question: str,
        sql: str,
        error_message: str,
        schema: str,
    ) -> str:
        """构建 SQL 自动修复 Prompt。"""
        return self.sql_repair_prompt_template.format(
            schema=schema,
            question=question,
            sql=sql,
            error=error_message,
        )

    @staticmethod
    def clean_sql(content: str) -> str:
        """移除大模型可能返回的 Markdown 代码块标记。"""
        content = content.strip()

        if content.startswith("```sql"):
            content = content[6:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        return content.strip()

    def generate_sql(self, question: str, schema: str) -> str:
        """调用大模型生成 SQL。"""
        prompt = self.build_sql_prompt(question, schema)

        response = self.llm.invoke(prompt)

        return self.clean_sql(response.content)

    def repair_sql(
        self,
        question: str,
        sql: str,
        error_message: str,
        schema: str,
    ) -> str:
        """根据数据库错误信息调用大模型修复 SQL。"""
        prompt = self.build_repair_prompt(
            question=question,
            sql=sql,
            error_message=error_message,
            schema=schema,
        )

        response = self.llm.invoke(prompt)

        return self.clean_sql(response.content)

    @staticmethod
    def summarize_result(rows: list[dict[str, Any]]) -> str:
        """将数据库查询结果转换成简单的自然语言回答。"""
        if not rows:
            return "查询完成，但没有找到符合条件的数据。"

        if len(rows) == 1 and len(rows[0]) == 1:
            value = next(iter(rows[0].values()))
            return f"查询结果是：{value}。"

        result_text = json.dumps(
            rows,
            ensure_ascii=False,
            default=str,
        )

        return f"查询完成，共返回 {len(rows)} 条结果：{result_text}"

    def run(
        self,
        question: str,
        schema_context: str,
    ) -> dict[str, Any]:
        """
        执行完整的 Text-to-SQL 流程。

        流程：
        1. 检查 Schema 是否为空。
        2. 调用大模型生成 SQL。
        3. 执行 SQL。
        4. 第一次失败后自动修复一次。
        5. 修复后仍失败则返回结构化错误。
        """
        if not schema_context.strip():
            return {
                "success": False,
                "question": question,
                "sql": None,
                "rows": [],
                "answer": "没有获得数据库结构，无法生成 SQL。",
                "repaired": False,
                "error_message": "schema_context 为空",
            }

        try:
            generated_sql = self.generate_sql(
                question=question,
                schema=schema_context,
            )
        except Exception as error:
            return {
                "success": False,
                "question": question,
                "sql": None,
                "rows": [],
                "answer": "大模型生成 SQL 时发生错误。",
                "repaired": False,
                "error_message": str(error),
            }

        repaired = False
        first_error_message = None

        try:
            # execute_sql 内部会先经过 SQL Guard 安全校验
            rows = execute_sql(generated_sql)

        except (SQLAlchemyError, ValueError) as first_error:
            # SQLAlchemyError：SQL 执行错误
            # ValueError：SQL Guard 拦截了不安全 SQL
            first_error_message = str(first_error)
            repaired = True

            try:
                # 将错误 SQL 和报错信息交给模型修复
                generated_sql = self.repair_sql(
                    question=question,
                    sql=generated_sql,
                    error_message=first_error_message,
                    schema=schema_context,
                )

                # 修复后的 SQL 仍然必须重新经过安全校验
                rows = execute_sql(generated_sql)

            except (SQLAlchemyError, ValueError) as second_error:
                return {
                    "success": False,
                    "question": question,
                    "sql": generated_sql,
                    "rows": [],
                    "answer": "SQL 自动修复后仍然无法执行，请重新描述问题。",
                    "repaired": True,
                    "error_message": str(second_error),
                    "first_error_message": first_error_message,
                }

            except Exception as repair_error:
                return {
                    "success": False,
                    "question": question,
                    "sql": generated_sql,
                    "rows": [],
                    "answer": "调用大模型修复 SQL 时发生错误。",
                    "repaired": True,
                    "error_message": str(repair_error),
                    "first_error_message": first_error_message,
                }

        answer = self.summarize_result(rows)

        return {
            "success": True,
            "question": question,
            "sql": generated_sql,
            "rows": rows,
            "answer": answer,
            "repaired": repaired,
            "error_message": first_error_message,
        }