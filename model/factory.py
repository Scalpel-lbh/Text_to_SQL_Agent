"""
文件作用：
    统一创建项目使用的大模型和 Embedding 模型。

主要功能：
    1. 创建通义千问聊天模型，用于 SQL 生成、修复和 Agent 推理。
    2. 创建文本向量模型，用于 Schema 文档向量化和语义检索。
    3. 集中管理模型配置，方便后续更换模型。
"""


# os 用于读取 DASHSCOPE_API_KEY 等环境变量
import os

# ChatTongyi 是 LangChain 封装的通义千问聊天模型
# DashScopeEmbeddings 是阿里云提供的文本向量模型
from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings


def get_dashscope_api_key() -> str:
    """读取并校验 DashScope API Key。"""
    api_key = os.getenv("DASHSCOPE_API_KEY")

    if not api_key:
        raise RuntimeError("请先配置环境变量 DASHSCOPE_API_KEY")

    return api_key


def create_chat_model() -> ChatTongyi:
    """创建聊天模型，用于 Agent 推理和 SQL 生成。"""
    return ChatTongyi(
        model="qwen-plus",
        temperature=0,
        dashscope_api_key=get_dashscope_api_key(),
    )


def create_embedding_model() -> DashScopeEmbeddings:
    """创建文本向量模型，用于 Schema RAG。"""
    return DashScopeEmbeddings(
        model="text-embedding-v4",
        dashscope_api_key=get_dashscope_api_key(),
    )