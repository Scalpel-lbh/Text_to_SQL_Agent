"""
文件作用：
管理 Schema RAG 使用的 Chroma 向量库。

主要功能：
1. 读取数据库 Schema 文档。
2. 将每张表转换成一个 LangChain Document。
3. 将 Schema 文档向量化并存入 Chroma。
4. 根据用户问题执行 Top-K 语义检索。
5. 根据表关联关系自动补充语义检索遗漏的关联表。
"""

# json：读取并解析 Schema JSON 文件
import json

# Path：定位 Schema 文件和 Chroma 持久化目录
from pathlib import Path

# Document：LangChain 文档对象，保存文本内容和元数据
from langchain_core.documents import Document

# Chroma：LangChain 封装的 Chroma 向量数据库
from langchain_chroma import Chroma

# create_embedding_model：创建文本向量模型
from model.factory import create_embedding_model


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# Schema 原始数据文件
SCHEMA_DOCUMENTS_PATH = BASE_DIR / "data" / "schema_documents.json"

# Chroma 持久化目录
CHROMA_PATH = BASE_DIR / "data" / "schema_chroma_db"

# Chroma 集合名称
COLLECTION_NAME = "database_schema"


class SchemaStore:
    """负责 Schema 文档的向量存储、语义检索和关联表扩展。"""

    def __init__(self) -> None:
        # 读取结构化 Schema 数据
        self.schema_data = json.loads(
            SCHEMA_DOCUMENTS_PATH.read_text(encoding="utf-8")
        )

        # 通过表名快速查找对应的 Schema 数据
        self.schema_by_table = {
            table["table_name"]: table
            for table in self.schema_data
        }

        # 将每张表提前转换成 Document
        self.documents_by_table = {
            document.metadata["table_name"]: document
            for document in self.load_schema_documents()
        }

        # 创建 Embedding 模型
        embedding_model = create_embedding_model()

        # 创建或加载本地 Chroma 向量库
        self.vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embedding_model,
            persist_directory=str(CHROMA_PATH),
        )

    def load_schema_documents(self) -> list[Document]:
        """将每张表的 Schema 数据转换成一个 Document。"""
        documents = []

        for table in self.schema_data:
            column_lines = [
                f"- {column_name}：{description}"
                for column_name, description in table["columns"].items()
            ]

            relation_lines = [
                f"- {relation}"
                for relation in table.get("relations", [])
            ]

            rule_lines = [
                f"- {rule}"
                for rule in table.get("business_rules", [])
            ]

            content_parts = [
                f"表名：{table['table_name']}",
                f"表说明：{table['description']}",
                "字段说明：",
                "\n".join(column_lines),
            ]

            if relation_lines:
                content_parts.extend([
                    "关联关系：",
                    "\n".join(relation_lines),
                ])

            if rule_lines:
                content_parts.extend([
                    "业务规则：",
                    "\n".join(rule_lines),
                ])

            document = Document(
                page_content="\n".join(content_parts),
                metadata={
                    "table_name": table["table_name"],
                    "document_type": "database_schema",
                },
            )

            documents.append(document)

        return documents

    def initialize(self) -> None:
        """首次运行时将 Schema 文档写入 Chroma。"""
        stored_data = self.vector_store.get(include=[])

        if stored_data["ids"]:
            print(
                f"Schema 向量库已存在，"
                f"共 {len(stored_data['ids'])} 条文档"
            )
            return

        documents = list(self.documents_by_table.values())

        document_ids = [
            document.metadata["table_name"]
            for document in documents
        ]

        self.vector_store.add_documents(
            documents=documents,
            ids=document_ids,
        )

        print(
            f"Schema 向量库初始化完成，"
            f"共写入 {len(documents)} 条文档"
        )

    def get_related_table_names(self, table_name: str) -> list[str]:
        """
        获取某张表直接关联的表名。

        relations 当前是自然语言，例如：
        order_items.order_id 与 orders.id 关联

        因为所有合法表名都保存在 schema_by_table 中，
        所以可以检查关联描述中出现了哪些已知表名。
        """
        table_data = self.schema_by_table.get(table_name)

        if not table_data:
            return []

        related_tables = []

        for relation in table_data.get("relations", []):
            for candidate_table in self.schema_by_table:
                # 使用“表名.”避免普通单词误匹配
                table_identifier = f"{candidate_table}."

                if (
                    candidate_table != table_name
                    and table_identifier in relation
                    and candidate_table not in related_tables
                ):
                    related_tables.append(candidate_table)

        return related_tables

    def search(
        self,
        query: str,
        k: int = 3,
    ) -> list[Document]:
        """
        执行 Schema 检索。

        第一步：通过 Chroma 找到 Top-K 语义相关表。
        第二步：根据 relations 补充这些表直接关联的表。
        """
        semantic_documents = self.vector_store.similarity_search(
            query=query,
            k=k,
        )

        result_documents = []
        selected_table_names = set()

        # 先保存 Chroma 直接检索出的表
        for document in semantic_documents:
            table_name = document.metadata["table_name"]

            if table_name in selected_table_names:
                continue

            result_documents.append(
                Document(
                    page_content=document.page_content,
                    metadata={
                        **document.metadata,
                        "retrieval_source": "semantic_search",
                    },
                )
            )

            selected_table_names.add(table_name)

        # 再补充直接关联的表，只扩展一层，防止范围无限扩大
        for document in semantic_documents:
            table_name = document.metadata["table_name"]

            related_table_names = self.get_related_table_names(
                table_name
            )

            for related_table_name in related_table_names:
                if related_table_name in selected_table_names:
                    continue

                related_document = self.documents_by_table[
                    related_table_name
                ]

                result_documents.append(
                    Document(
                        page_content=related_document.page_content,
                        metadata={
                            **related_document.metadata,
                            "retrieval_source": "relation_expansion",
                        },
                    )
                )

                selected_table_names.add(related_table_name)

        return result_documents


if __name__ == "__main__":
    schema_store = SchemaStore()
    schema_store.initialize()

    results = schema_store.search(
        query="销售额最高的商品是什么？",
        k=3,
    )

    print("\n检索结果：")

    for index, document in enumerate(results, start=1):
        print(f"\n第 {index} 条：")
        print(f"对应表：{document.metadata['table_name']}")
        print(f"检索来源：{document.metadata['retrieval_source']}")
        print(document.page_content)