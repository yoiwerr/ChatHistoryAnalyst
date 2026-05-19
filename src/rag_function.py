# src/rag_function.py
import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from typing import List
from src.schemas import ChatMessage
from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector

load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = os.getenv("DASHSCOPE_BASE_URL")
pgpass = os.getenv("PGSQLPASSWORD")

# ==========================================
# 1. 数据库与 Embedding 配置
# ==========================================
# 注意：替换为你真实的 PG 数据库账号密码
CONNECTION_STRING = f"postgresql+psycopg2://postgres:{pgpass}@localhost:5432/chatdemopg"

embeddings = OpenAIEmbeddings(
    model = "text-embedding-v1",
    openai_api_key = api_key,
    openai_api_base = base_url
)

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

    # 将 Pydantic 的 ChatMessage 对象转换为 LangChain 的 Document 格式
    # 为了方便检索，我们在文本中加入目标人物的标签
    docs = []
    for chat in recent_chats:
        content = f"[{chat.timestamp}] {chat.sender}: {chat.content}"

        # 封装为 Document，可以在 metadata 中存入额外信息（利用 PGVector 的 JSONB 特性）
        doc = Document(
            page_content=content,
            metadata={
                "target_person": target_person,
                "sender": chat.sender,
                "type": "chat_history"
            }
        )
        docs.append(doc)

    # 存入聊天记录专属的向量库集合中
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

    # 检查是否已导入过（按 source 文件名匹配）
    try:
        existing = knowledge_store.similarity_search(" ", k=1, filter={"source": file_name})
        if existing:
            return f"文件 {file_name} 已导入过（检测到同名 source），跳过。"
    except Exception:
        pass  # 首次调用时 collection 可能为空，忽略

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