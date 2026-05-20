# src/rag_function.py
import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from typing import List
from src.schemas import ChatMessage

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_postgres.vectorstores import PGVector
from sqlalchemy import create_engine, text

load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")
pgpass = os.getenv("PGSQLPASSWORD")

# ==========================================
# 1. 数据库与 Embedding 配置
# ==========================================
CONNECTION_STRING = os.getenv(
    "POSTGRES_URL",
    f"postgresql+psycopg2://postgres:{pgpass}@localhost:5432/chatdemopg"
)

embeddings = DashScopeEmbeddings(
    model="qwen3-rerank",
    dashscope_api_key=api_key
)


def _get_embedding_dim() -> int:
    """返回当前嵌入模型输出的向量维度。"""
    return len(embeddings.embed_query("test"))


def _get_stored_vector_dim() -> int | None:
    """查询 pgvector 表中已存储向量的维度，若无数据则返回 None。"""
    engine = None
    try:
        engine = create_engine(CONNECTION_STRING)
        with engine.connect() as conn:
            exists = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = 'langchain_pg_embedding')"
            ))
            if not exists.fetchone()[0]:
                return None
            row = conn.execute(text(
                "SELECT vector_dims(embedding) FROM langchain_pg_embedding LIMIT 1"
            ))
            result = row.fetchone()
            if result:
                return result[0]
    except Exception:
        pass
    finally:
        if engine:
            engine.dispose()
    return None


def _fix_dimension_mismatch():
    """检测向量维度是否匹配，不匹配则清空旧表以便重建。"""
    stored_dim = _get_stored_vector_dim()
    if stored_dim is None:
        return
    current_dim = _get_embedding_dim()
    if stored_dim != current_dim:
        print(f"⚠️ 向量维度不匹配: 表中={stored_dim}, 当前模型={current_dim}。正在清空旧数据...")
        engine = None
        try:
            engine = create_engine(CONNECTION_STRING)
            with engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS langchain_pg_collection CASCADE"))
                conn.commit()
            print("✅ 旧向量表已清除，下次写入时将使用正确维度重建。")
            print("📌 请重新导入知识文件: POST /api/v1/import_knowledge?file_name=DBL.txt 等")
        except Exception as e:
            print(f"清除旧向量表失败: {e}")
        finally:
            if engine:
                engine.dispose()


# 模块加载时自动检测并修复维度不匹配
_fix_dimension_mismatch()

# 【永久库】：心理学资料、理论文献
knowledge_store = PGVector(
    embeddings=embeddings,
    collection_name="psychology_knowledge",
    connection=CONNECTION_STRING,
    use_jsonb=True
)

# 【历史库】：聊天记录（持久积累，不再清空）
chat_history_store = PGVector(
    embeddings=embeddings,
    collection_name="chat_history",
    connection=CONNECTION_STRING,
    use_jsonb=True
)


def save_chats_to_long_term_memory(recent_chats: List[ChatMessage], target_person: str) -> str:
    """
    将前端传入的聊天记录永久存入向量知识库，作为该人物的长期记忆。
    """
    if not recent_chats:
        return "没有接收到聊天记录。"

    docs = []
    for chat in recent_chats:
        content = f"[{chat.timestamp}] {chat.sender}: {chat.content}"

        doc = Document(
            page_content=content,
            metadata={
                "target_person": target_person,
                "sender": chat.sender,
                "type": "chat_history"
            }
        )
        docs.append(doc)

    try:
        chat_history_store.add_documents(docs)
        return f"成功将 {len(docs)} 条关于 {target_person} 的聊天记录存入长期记忆库！"
    except Exception as e:
        print(f"写入向量库失败: {e}")
        return f"保存失败，数据库发生错误: {str(e)}"

def import_knowledge_file(file_name: str) -> str:
    """
    将 data/ 目录下的 txt 资料文件切块导入心理学知识库 (knowledge_store)。
    调用一次即可，重复调用同一文件会跳过。
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    file_path = os.path.join(os.path.dirname(__file__), "..", "data", file_name)
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"

    try:
        existing = knowledge_store.similarity_search(" ", k=1, filter={"source": file_name})
        if existing:
            return f"文件 {file_name} 已导入过（检测到同名 source），跳过。"
    except Exception:
        pass

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.strip():
        return f"文件 {file_name} 为空，跳过。"

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
    )

    chunks = text_splitter.split_text(text)
    docs = [
        Document(page_content=chunk, metadata={"source": file_name, "type": "reference_book"})
        for chunk in chunks
    ]

    try:
        knowledge_store.add_documents(docs)
        return f"成功将 {file_name} 导入知识库，共 {len(chunks)} 个文本块。"
    except Exception as e:
        return f"导入失败: {str(e)}"


def list_imported_files() -> list:
    """列出已导入知识库的资料文件名（去重）。"""
    try:
        results = knowledge_store.similarity_search(" ", k=100, filter={"type": "reference_book"})
        sources = list(set(doc.metadata.get("source", "unknown") for doc in results))
        return sources
    except Exception:
        return []