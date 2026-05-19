# src/rag_function.py
from src.tools import chat_history_store, knowledge_store
from langchain_core.documents import Document
from typing import List
from src.schemas import ChatMessage


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

# 预留位置：以后处理 TXT 或多模态文件的函数也可以写在这里
# def save_txt_to_knowledge_base(file_path: str):
#     pass