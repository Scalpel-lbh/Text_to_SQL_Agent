"""
文件作用：
对大模型生成的 SQL 进行安全校验。

主要功能：
1. 拒绝空 SQL。
2. 只允许执行一条 SQL。
3. 只允许 SELECT 或 WITH 查询。
4. 拦截修改数据库结构或数据的危险关键词。
"""


# re：Python 正则表达式模块，用于匹配 SQL 关键词
import re


# 禁止出现在 SQL 中的危险关键词
FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "truncate",
    "attach",
    "detach",
    "pragma",
    "vacuum",
}


def validate_select_sql(sql: str) -> tuple[bool, str]:
    """
    检查 SQL 是否为安全的只读查询。

    返回：
        bool：是否通过校验。
        str：校验结果或错误原因。
    """
    cleaned_sql = sql.strip()

    if not cleaned_sql:
        return False, "SQL 不能为空"

    # 移除最后一个可选的分号，便于判断是否包含多条语句
    sql_without_tail_semicolon = (
        cleaned_sql[:-1]
        if cleaned_sql.endswith(";")
        else cleaned_sql
    )

    # 中间仍存在分号，说明可能包含多条 SQL
    if ";" in sql_without_tail_semicolon:
        return False, "只允许执行单条 SQL 语句"

    # 只允许普通 SELECT，或者以 WITH 开头的 CTE 查询
    if not re.match(
        r"^\s*(select|with)\b",
        cleaned_sql,
        flags=re.IGNORECASE,
    ):
        return False, "只允许执行 SELECT 查询语句"

    # 拦截危险关键词
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{keyword}\b"

        if re.search(
            pattern,
            cleaned_sql,
            flags=re.IGNORECASE,
        ):
            return False, f"SQL 中包含禁止关键词：{keyword}"

    return True, "SQL 校验通过"


if __name__ == "__main__":
    test_sql_list = [
        "SELECT * FROM users",
        "SELECT name FROM products;",
        "WITH paid_orders AS (SELECT * FROM orders) "
        "SELECT * FROM paid_orders",
        "DELETE FROM users",
        "DROP TABLE users",
        "VACUUM",
        "SELECT * FROM users; DROP TABLE users;",
        "",
    ]

    for test_sql in test_sql_list:
        is_valid, message = validate_select_sql(test_sql)

        print(f"SQL：{test_sql}")
        print(f"是否通过：{is_valid}")
        print(f"校验结果：{message}")
        print("-" * 50)