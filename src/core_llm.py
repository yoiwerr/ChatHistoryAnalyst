import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from src.tools import ALL_TOOLS
load_dotenv()

base_url = os.getenv("DASHSCOPE_BASE_URL")
api_key = os.getenv("DASHSCOPE_API_KEY")

if not api_key:
    raise ValueError("未在环境变量中找到 DASHSCOPE_API_KEY，请检查 .env 文件。")

base_llm = init_chat_model(
    model="qwen3-max",
    model_provider="openai",
    base_url=base_url,
    api_key=api_key,
)
llm = base_llm.bind_tools(ALL_TOOLS)