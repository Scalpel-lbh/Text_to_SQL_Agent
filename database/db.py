"""
文件作用：
    这个文件负责数据库访问。

主要功能：
    1. 连接 SQLite 数据库。
    2. 获取数据库表结构，供大模型生成 SQL 时参考。
    3. 执行 SQL 查询，并返回字典列表结果。
    4. 在执行 SQL 前调用安全校验，禁止危险 SQL 操作。
"""
from pathlib import Path
from sqlalchemy import create_engine,text,inspect

from utils.sql_guard import validate_select_sql
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ecommerce.db"
# sqlAlchemy连接sqlite数据库
DATABASE_URL = f"sqlite:///{DB_PATH}"

#创建数据库连接引擎
engine = create_engine(
    DATABASE_URL,
    echo=False
)


def get_schema_info() -> str:
    """获取数据库表结构信息，后续会放进 Prompt 里给大模型参考。"""
    inspector = inspect(engine)
    schema_lines = []

    for table_name in inspector.get_table_names():
        schema_lines.append(f"表名:{table_name}")

        for column in inspector.get_columns(table_name):
            column_name = column['name']
            column_type = column['type']
            schema_lines.append(f"-{column_name}:{column_type}")
        
        schema_lines.append("")

    return "\n".join(schema_lines)


def execute_sql(sql:str) ->list[dict]:
    #sql检验
    is_valid,message = validate_select_sql(sql)
    if not is_valid:
        raise ValueError(message)
    
    #with执行后会自动关闭
    with engine.connect() as conn:
        result = conn.execute(text(sql))

        rows = result.mappings().all()

        return [dict(row) for row in rows]

if __name__ == "__main__":
    print("数据库表结构：")
    print(get_schema_info())

    print("安全查询测试：")
    rows = execute_sql("""
        SELECT products.name, SUM(products.price * order_items.quantity) AS total_sales
        FROM order_items
        JOIN products ON order_items.product_id = products.id
        GROUP BY products.name
        ORDER BY total_sales DESC
        LIMIT 3
    """)
    print(rows)

    print("危险查询测试：")
    try:
        execute_sql("DROP TABLE users")
    except ValueError as error:
        print(f"已拦截危险 SQL：{error}")