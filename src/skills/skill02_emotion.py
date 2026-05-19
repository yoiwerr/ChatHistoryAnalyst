# src/skills/skill02_emotion.py
from fastapi import HTTPException
from src.schemas import AnalysisRequest, EmotionResponse
from src.core_llm import base_llm
from src.tools import ALL_TOOLS, inject_chats_to_temp_db
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent

agent_executor = create_agent(model=base_llm, tools=ALL_TOOLS)
structured_llm = base_llm.with_structured_output(EmotionResponse)


async def execute_emotion_skill(request: AnalysisRequest) -> EmotionResponse:
    if not request.recent_chat:
        raise HTTPException(status_code=400, detail="分析失败：近期聊天记录不能为空。")

    try:
        docs = [Document(page_content=f"[{c.timestamp}] {c.sender}: {c.content}") for c in request.recent_chat]
        inject_chats_to_temp_db(docs)

        chat_context = "\n".join([f"[{c.timestamp}] {c.sender}: {c.content}" for c in request.recent_chat])

        sys_msg = SystemMessage(content="你是一个高级心理分析师。请调用 search_psychology_knowledge 搜索相关的心理学理论，"
                                        "并结合上下文，深度分析目标人物在对话中的情感状态。")
        user_msg = HumanMessage(content=f"目标人物：{request.target_person}\n"
                                        f"补充背景：{request.background_info}\n"
                                        f"当前聊天内容：\n{chat_context}\n\n"
                                        f"请分析 {request.target_person} 当前的情感状态，列出主导情绪、情感得分依据及心理学动因。")

        agent_response = await agent_executor.ainvoke({"messages": [sys_msg, user_msg]})
        analysis_report = agent_response["messages"][-1].content

        final_result = await structured_llm.ainvoke(
            f"根据以下心理学分析报告，提取出符合结构化要求的数据:\n\n{analysis_report}"
        )
        return final_result

    except Exception as e:
        # 如果是 Pydantic 解析 JSON 失败，或者大模型连不上，都会在这里被捕获
        print(f"Error in emotion skill: {str(e)}")
        raise HTTPException(status_code=500, detail=f"情感分析执行失败，可能是服务超时或格式化错误：{str(e)}")