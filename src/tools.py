# src/tools.py
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_classic.agents import create_react_agent
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_community.tools.tavily_search import TavilySearchResults

# 加载环境变量
load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = os.getenv("DASHSCOPE_BASE_URL")
pgpass = os.getenv("PGSQLPASSWORD")

# ==========================================
# 1. 数据库与 Embedding 配置
# ==========================================
# 注意：替换为你真实的 PG 数据库账号密码
CONNECTION_STRING = f"postgresql+psycopg2://postgres:{pgpass}@localhost:5432/chatdemopg"

model = init_chat_model(
    model="text-embedding-async-v1",
    model_provider = "openai",
    base_url = base_url,
    api_key = api_key
)

embeddings = OpenAIEmbeddings(
    model= model,

)

# 【永久库】：心理学资料、理论文献
knowledge_store = PGVector(
    embeddings=embeddings,
    collection_name="psychology_knowledge",
    connection=CONNECTION_STRING,
    use_jsonb=True
)

# 【临时库】：历史聊天记录
chat_history_store = PGVector(
    embeddings=embeddings,
    collection_name="chat_history_temp",
    connection=CONNECTION_STRING,
    use_jsonb=True
)

# ==========================================
# 2. 定义 Agent 可以调用的 Tools
# 注意：函数下方的注释 (Docstring) 是给大模型看的，千万不要删，模型靠它决定何时调用！
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

# 3. 联网搜索工具 (Tavily)
# 我们直接使用 LangChain 封装好的 Tavily 工具，并为它加上中文描述
tavily_tool = TavilySearchResults(max_results=3)
tavily_tool.name = "web_search"
tavily_tool.description = """
当你需要搜索最新的心理学论文、网络流行语的含义、或者遇到本地知识库无法解答的外部实时信息时，调用此工具进行全网搜索。
"""
a = create_react_agent((

))
# 统一导出所有工具
ALL_TOOLS = [search_psychology_knowledge, search_chat_history, tavily_tool]

# ==========================================
# 4. 辅助函数：用于在分析前，将当前的聊天记录动态写入临时库
# ==========================================
def inject_chats_to_temp_db(documents):
    """
    在执行技能前调用此函数，将聊天记录转为 Document 列表存入 chat_history_temp 库。
    为了保持是临时库，你可以选择在插入前先清空旧数据。
    """
    # 清空旧数据的简单逻辑（根据你的需求决定是否保留长期记忆）
    chat_history_store.drop_tables()
    # 重新存入当前对话
    chat_history_store.add_documents(documents)
    print("✅ 历史聊天记录已存入临时向量库！")