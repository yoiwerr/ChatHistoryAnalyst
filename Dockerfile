FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    dashscope fastapi langchain langchain-community langchain-openai \
    "langchain-postgres[async]" langchain-tavily langchain-text-splitters \
    psycopg2-binary pydantic python-dotenv requests streamlit uvicorn

COPY . .
