# src/skills/skill03_atmosphere.py
from fastapi import HTTPException
from src.schemas import AnalysisRequest, AtmosphereResponse
from src.core_llm import base_llm
from src.tools import ALL_TOOLS, inject_chats_to_temp_db
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent

agent_executor = create_agent(model=base_llm, tools=ALL_TOOLS)
structured_llm = base_llm.with_structured_output(AtmosphereResponse)


async def execute_atmosphere_skill(request: AnalysisRequest) -> AtmosphereResponse:
    if not request.recent_chat:
        raise HTTPException(status_code=400, detail="分析失败：近期聊天记录不能为空。")

    try:
        docs = [Document(page_content=f"[{c.timestamp}] {c.sender}: {c.content}") for c in request.recent_chat]
        inject_chats_to_temp_db(docs)

        chat_context = "\n".join([f"[{c.timestamp}] {c.sender}: {c.content}" for c in request.recent_chat])

        sys_msg = SystemMessage(content="你是一名资深的人际关系与谈判专家。请按以下步骤进行分析：\n"
                                        "1. 先调用 search_chat_history 检索双方在数据库中的全部历史聊天记录，"
                                        "判断长期的关系模式和权力动态演变趋势。\n"
                                        "2. 再调用 search_psychology_knowledge 获取人际动态、权力博弈相关的心理学理论，"
                                        "结合历史背景和当前对话内容，深度剖析当前聊天气氛及权力结构。\n"
                                        "3. 如有需要，可调用 web_search 获取相关的外部参考信息。")
        user_msg = HumanMessage(content=f"目标人物：{request.target_person}\n"
                                        f"补充背景：{request.background_info}\n"
                                        f"当前聊天内容：\n{chat_context}\n\n"
                                        f"请深度剖析当前的聊天气氛、权力动态，并给出应对建议。")

        agent_response = await agent_executor.ainvoke({"messages": [sys_msg, user_msg]})
        analysis_report = agent_response["messages"][-1].content

        final_result = await structured_llm.ainvoke(
            f"根据以下专家分析报告，提取结构化数据:\n\n{analysis_report}"
        )
        return final_result

    except Exception as e:
        print(f"Error in atmosphere skill: {str(e)}")
        raise HTTPException(status_code=500, detail=f"气氛分析执行失败，可能是服务超时或数据库异常：{str(e)}")