# src/tools.py
from langchain_core.tools import tool
# 1. 换回最新版推荐的导入方式，消除警告
from langchain_tavily import TavilySearch
from src.rag_function import knowledge_store, save_chats_to_long_term_memory, chat_history_store


# ==========================================
# 2. 定义 Agent 可以调用的 Tools
# ==========================================

@tool
def search_psychology_knowledge(query: str) -> str:
    """
    当需要分析聊天记录背后的心理学动机、进行情感分析、气氛分析，或需要专业的心理学理论和沟通建议时，必须调用此工具。
    输入参数 query 应该是你想查询的心理学关键词或现象描述。
    """
    print(f"🛠️ [Tool调用] 正在知识库中检索: {query}")
    results = knowledge_store.similarity_search(query, k=3)
    if not results:
        return "本地心理学知识库中未找到相关内容。"
    return "\n\n".join([f"理论参考: {doc.page_content}" for doc in results])


@tool
def search_chat_history(query: str) -> str:
    """
    用于检索历史聊天记录。当需要模仿某人说话语气，或者需要了解他们之前的聊天上下文、前情提要时，必须调用此工具。
    输入参数 query 应该是具体的话题或你想寻找的对方的历史发言特征。
    """
    print(f"🛠️ [Tool调用] 正在历史记录中检索: {query}")
    results = chat_history_store.similarity_search(query, k=5)
    if not results:
        return "未找到相关的历史聊天记录。"
    return "\n".join([f"历史记录: {doc.page_content}" for doc in results])


# ==========================================
# 3. 封装联网搜索工具 (强制返回纯文本字符串防止大模型 400 报错)
# ==========================================
# 2. 初始化最新版的 TavilySearch
_raw_tavily = TavilySearch(max_results=3)


@tool
def web_search(query: str) -> str:
    """
    当你需要搜索最新的心理学论文、网络流行语的含义、或者遇到本地知识库无法解答的外部实时信息时，调用此工具进行全网搜索。
    输入参数 query 是你要搜索的关键词。
    """
    print(f"🛠️ [Tool调用] 正在联网检索: {query}")
    try:
        # 调用底层工具获取数据
        results = _raw_tavily.invoke({"query": query})

        # 强制转换为纯文本字符串
        if isinstance(results, list):
            text_results = []
            for idx, r in enumerate(results):
                if isinstance(r, dict):
                    content = r.get("content", "")
                    text_results.append(f"结果{idx + 1}: {content}")
            return "\n\n".join(text_results) if text_results else "未找到相关网络信息。"

        # 如果是其他类型，直接强转字符串
        return str(results)

    except Exception as e:
        return f"联网搜索失败: {str(e)}"


# 统一导出所有工具
ALL_TOOLS = [search_psychology_knowledge, search_chat_history, web_search]