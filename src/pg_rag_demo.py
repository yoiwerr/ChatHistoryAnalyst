# src/pg_rag_demo.py
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# 加载环境变量
load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = os.getenv("DASHSCOPE_BASE_URL")
pgpass = os.getenv("PGSQLPASSWORD")

model = init_chat_model(
    model="text-embedding-async-v1",
    model_provider = "openai",
    base_url = base_url,
    api_key = api_key
)


# 1. 配置数据库连接
# TODO: 请将下面的用户名、密码、端口和数据库名(chat_db)替换为你本地的真实配置
# 格式: postgresql+psycopg2://用户名:密码@主机地址:端口/数据库名
CONNECTION_STRING = f"postgresql+psycopg2://postgres:{pgpass}@localhost:5432/chatdemopg"
COLLECTION_NAME = "psychology_docs"  # 这相当于你的数据表名


# 2. 初始化 Embedding 模型
embeddings = OpenAIEmbeddings(
    model="text-embedding-async-v1",

)


# 3. 建立 PostgreSQL 向量数据库连接
# 注意：如果数据库中不存在所需的表，LangChain 会自动为你创建
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
    use_jsonb=True  # 开启 JSONB 支持，方便以后存储聊天记录的元数据(如 sender, time)
)


def init_and_insert_data():
    """第一步：处理文本并存入 PostgreSQL"""
    print("开始处理数据并存入 PostgreSQL...🚀 ")

    raw_text = """
    【心理学知识】：当一个人在聊天中频繁使用“随便”、“都行”时，这不仅代表随和，
    在心理学上，如果伴随回复时间变长，往往意味着防御心理增强，或者对当前话题失去了兴趣。

    【聊天记录】：张三说，最近工作压力真的太大了，老板天天画大饼。
    【聊天记录】：张三说，我昨晚又失眠了，感觉快扛不住了。
    """

    # 构造文档并切分
    doc = Document(page_content=raw_text)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
    docs = text_splitter.split_documents([doc])

    # 存入数据库
    vector_store.add_documents(docs)
    print(f"✅ 成功将 {len(docs)} 个文本块存入 PostgreSQL 数据库的 '{COLLECTION_NAME}' 集合中！\n")


def test_search():
    """第二步：从 PostgreSQL 中进行向量检索"""
    query = "张三最近遇到什么烦心事了？"
    print(f"❓ 模拟提问: {query}")

    # 检索最相关的 2 条记录
    results = vector_store.similarity_search(query, k=2)

    print("💡 PostgreSQL 检索到的相关内容：")
    for i, res in enumerate(results):
        print(f"片段 {i + 1}: {res.page_content}")


if __name__ == "__main__":
    # 1. 存入数据（第一次运行后，如果不想重复存入，可以把这行注释掉）
    init_and_insert_data()

    # 2. 检索数据
    test_search()