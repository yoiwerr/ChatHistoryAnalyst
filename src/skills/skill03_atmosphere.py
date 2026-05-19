# src/skills/skill03_atmosphere.py
import json
from fastapi import HTTPException
from src.schemas import AnalysisRequest, AtmosphereResponse
from src.core_llm import base_llm
from src.tools import ALL_TOOLS
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent

agent_executor = create_agent(model=base_llm, tools=ALL_TOOLS)

ATMOSPHERE_SCHEMA_STR = json.dumps({
    "atmosphere_summary": "str (对当前聊天气氛的整体简短总结，如 紧张僵持/单方面迎合/轻松暧昧)",
    "power_dynamic": "str (双方权力动态深度分析：指出是否有哪一方过于迎合/软弱/处于劣势，并给出判断依据)",
    "actionable_suggestions": "list[str] (至少2条具体的沟通建议，如 如何改善卑微姿态/如何不卑不亢地夺回话语权)"
}, ensure_ascii=False)


async def execute_atmosphere_skill(request: AnalysisRequest) -> AtmosphereResponse:
    if not request.recent_chat:
        raise HTTPException(status_code=400, detail="分析失败：近期聊天记录不能为空。")

    try:
        chat_context = "\n".join(
            [f"[{c.timestamp}] {c.sender}: {c.content}" for c in request.recent_chat]
        )

        sys_msg = SystemMessage(content=f"""你是资深人际关系与谈判专家。按以下步骤完成任务：

步骤1: 调用 search_chat_history 检索 {request.target_person} 及双方在数据库中的全部历史聊天记录，判断长期的关系模式和权力动态演变趋势。
步骤2: 调用 search_psychology_knowledge 获取人际动态、权力博弈、沟通姿态相关的心理学理论，作为分析依据。
步骤3: 如有需要，可调用 web_search 获取额外的外部参考信息。
步骤4: 综合分析后，以 JSON 格式输出最终结果。JSON Schema 如下：
{ATMOSPHERE_SCHEMA_STR}

只输出 JSON，不要有其他文字。""")

        user_msg = HumanMessage(content=f"""目标人物：{request.target_person}
补充背景：{request.background_info or "无"}
当前聊天内容：
{chat_context}

请按照以上步骤进行分析，最终以 JSON 格式直接输出结果。""")

        result = await agent_executor.ainvoke({"messages": [sys_msg, user_msg]})
        raw_output = result["messages"][-1].content

        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0]
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0]

        return AtmosphereResponse.model_validate_json(raw_output.strip())

    except Exception as e:
        import traceback
        print(f"Error in atmosphere skill: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"气氛分析执行失败: {str(e)}")
