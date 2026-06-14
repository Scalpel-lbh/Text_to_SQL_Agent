"""
文件作用：
    创建并管理 Redis 客户端连接。

主要功能：
    1. 从环境变量读取 Redis 连接配置。
    2. 创建可被其他模块复用的 Redis 客户端。
    3. 提供 Redis 连接测试功能。
"""
import os
import redis
# 从环境变量读取配置；未配置时使用本地开发默认值
REDIS_HOST = os.getenv("REDIS_HOST","localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT","6379"))
REDIS_DB = int(os.getenv("REDIS_DB","0"))

redis_client = redis.Redis(
    host = REDIS_HOST,
    port = REDIS_PORT,
    db = REDIS_DB,
    decode_responses = True
)

def check_redis_connection() -> bool:
    """通过 PING 命令检查 Redis 是否连接成功。"""
    return redis_client.ping()


if __name__ == "__main__":
    if check_redis_connection():
        print("Redis 连接成功")