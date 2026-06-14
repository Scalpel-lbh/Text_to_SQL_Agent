from pathlib import Path

from sqlalchemy import create_engine, text


# 获取项目根目录：Text_to_SQL_Agent/
BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite 数据库文件保存位置：data/ecommerce.db
DB_PATH = BASE_DIR / "data" / "ecommerce.db"

# SQLAlchemy 连接 SQLite 的数据库地址
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建数据库连接引擎，后续建表、插入数据、查询都通过 engine 执行
engine = create_engine(DATABASE_URL, echo=False)


def init_database() -> None:
    """初始化电商 SQLite 数据库，包括建表和插入样例数据。"""
    # 确保 data/ 目录存在，否则 SQLite 无法创建 ecommerce.db 文件
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # engine.begin() 会自动开启事务：
    # 全部执行成功则提交；中间报错则回滚，避免数据库处于半初始化状态
    with engine.begin() as conn:
        # 先删除子表，再删除父表，避免外键依赖导致删除失败
        conn.execute(text("DROP TABLE IF EXISTS order_items"))
        conn.execute(text("DROP TABLE IF EXISTS orders"))
        conn.execute(text("DROP TABLE IF EXISTS products"))
        conn.execute(text("DROP TABLE IF EXISTS users"))

        # 用户表：保存用户基本信息
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))

        # 商品表：保存商品名称、品类和单价
        conn.execute(text("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL
            )
        """))

        # 订单表：保存订单属于哪个用户、下单日期和订单状态
        conn.execute(text("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))

        # 订单明细表：保存一个订单里买了哪些商品、每种商品买了多少件
        conn.execute(text("""
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """))

        # 插入用户样例数据
        conn.execute(text("""
            INSERT INTO users (id, name, city, created_at) VALUES
            (1, 'Alice', '上海', '2026-01-10'),
            (2, 'Bob', '杭州', '2026-02-15'),
            (3, 'Cindy', '南京', '2026-03-20'),
            (4, 'David', '上海', '2026-04-05')
        """))

        # 插入商品样例数据
        conn.execute(text("""
            INSERT INTO products (id, name, category, price) VALUES
            (1, '智能手机', '数码', 3999),
            (2, '无线耳机', '数码', 499),
            (3, '扫地机器人', '家电', 2599),
            (4, '人体工学椅', '家具', 899),
            (5, '机械键盘', '数码', 699)
        """))

        # 插入订单样例数据
        conn.execute(text("""
            INSERT INTO orders (id, user_id, order_date, status) VALUES
            (1, 1, '2026-05-01', 'paid'),
            (2, 2, '2026-05-03', 'paid'),
            (3, 3, '2026-05-05', 'refunded'),
            (4, 1, '2026-05-10', 'paid'),
            (5, 4, '2026-06-01', 'paid')
        """))

        # 插入订单明细样例数据
        conn.execute(text("""
            INSERT INTO order_items (id, order_id, product_id, quantity) VALUES
            (1, 1, 1, 1),
            (2, 1, 2, 2),
            (3, 2, 3, 1),
            (4, 3, 4, 1),
            (5, 4, 5, 2),
            (6, 5, 3, 1),
            (7, 5, 2, 1)
        """))


if __name__ == "__main__":
    init_database()
    print(f"数据库初始化完成：{DB_PATH}")