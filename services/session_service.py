"""
文件作用：
    使用 Redis 管理企业数据分析 Agent 的多轮会话历史。

主要功能：
    1. 根据 session_id 区分不同聊天会话。
    2. 读取最近若干条用户和助手消息。
    3. 保存一轮用户问题和 Agent 回答。
    4. 限制历史消息数量，避免上下文无限增长。
    5. 设置会话过期时间，自动清理长期不活跃的数据。
    6. 支持主动清空会话。

Redis 数据结构：
    key：
        data_analysis_agent:session:{session_id}

    value：
        Redis List，每个元素是一条 JSON 格式的聊天消息。
"""


# json 用于在 Python 字典和 Redis 字符串之间转换
import json

# redis_client 是项目统一创建的 Redis 客户端
from utils.redis_client import redis_client


# Redis key 前缀，用于区分不同项目和不同业务数据
SESSION_KEY_PREFIX = "data_analysis_agent:session:"

# 最多保留最近 10 条消息，也就是大约 5 轮问答
MAX_HISTORY_MESSAGES = 10

# 会话 24 小时不活跃后自动过期
SESSION_TTL_SECONDS = 24 * 60 * 60


class SessionService:
    """负责 Redis 会话历史的读取、保存和清理。"""

    def build_session_key(self, session_id: str) -> str:
        """根据 session_id 生成完整的 Redis key。"""
        return f"{SESSION_KEY_PREFIX}{session_id}"

    def get_history(self, session_id: str) -> list[dict]:
        """读取当前会话最近的聊天历史。"""
        key = self.build_session_key(session_id)

        # 读取 Redis List 中的全部消息
        raw_messages = redis_client.lrange(key, 0, -1)

        # 将 JSON 字符串转换回 Python 字典
        return [
            json.loads(message)
            for message in raw_messages
        ]

    def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        """将一轮用户问题和 Agent 回答保存到 Redis。"""
        key = self.build_session_key(session_id)

        user_message = {
            "role": "user",
            "content": question,
        }

        assistant_message = {
            "role": "assistant",
            "content": answer,
        }

        # pipeline 将多条 Redis 命令集中提交，减少网络往返次数
        with redis_client.pipeline() as pipeline:
            # 将用户消息和助手消息依次追加到 List 尾部
            pipeline.rpush(
                key,
                json.dumps(user_message, ensure_ascii=False),
                json.dumps(assistant_message, ensure_ascii=False),
            )

            # 只保留最近 MAX_HISTORY_MESSAGES 条消息
            pipeline.ltrim(key, -MAX_HISTORY_MESSAGES, -1)

            # 每次写入消息后重新刷新 24 小时过期时间
            pipeline.expire(key, SESSION_TTL_SECONDS)

            # 执行 pipeline 中的全部命令
            pipeline.execute()

    def clear_history(self, session_id: str) -> None:
        """删除指定 session_id 的全部聊天历史。"""
        key = self.build_session_key(session_id)
        redis_client.delete(key)


if __name__ == "__main__":
    service = SessionService()
    test_session_id = "test_session"

    # 测试前先清除旧数据
    service.clear_history(test_session_id)

    # 保存两轮测试对话
    service.save_turn(
        test_session_id,
        "销售额最高的商品是什么？",
        "销售额最高的商品是扫地机器人。",
    )

    service.save_turn(
        test_session_id,
        "那它的销售额是多少？",
        "销售额为 5198 元。",
    )

    print("会话历史：")
    print(service.get_history(test_session_id))

    # 测试完成后清除测试数据
    service.clear_history(test_session_id)