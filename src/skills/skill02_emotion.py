# src/skills/skill02_emotion.py
import json
from fastapi import HTTPException
from src.schemas import AnalysisRequest, EmotionResponse
from src.core_llm import base_llm
from src.tools import ALL_TOOLS
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent

agent_executor = create_agent(model=base_llm, tools=ALL_TOOLS)

EMOTION_SCHEMA_STR = json.dumps({
    "emotion_score": "int (0-100, 0=极度消极, 50=中立, 100=极度积极)",
    "dominant_emotion": "str (主导情感标签, 如 焦虑/开心/冷漠/试探)",
    "analysis_reasoning": "str (详细分析推导过程)"
}, ensure_ascii=False)


async def execute_emotion_skill(request: AnalysisRequest) -> EmotionResponse:
    if not request.recent_chat:
        raise HTTPException(status_code=400, detail="分析失败：近期聊天记录不能为空。")

    try:
        chat_context = "\n".join(
            [f"[{c.timestamp}] {c.sender}: {c.content}" for c in request.recent_chat]
        )

        sys_msg = SystemMessage(content=f"""你是高级心理分析师。按以下步骤完成任务：

步骤1: 调用 search_chat_history 检索 {request.target_person} 在数据库中的所有历史发言，了解其长期沟通模式和情绪变化趋势。
步骤2: 调用 search_psychology_knowledge 搜索与当前对话内容相关的心理学理论，作为分析依据。
步骤3: 如涉及外部事件、网络流行语或需要实时信息补充，可调用 web_search。
步骤4: 综合分析后，以 JSON 格式输出最终结果。JSON Schema 如下：
{EMOTION_SCHEMA_STR}

只输出 JSON，不要有其他文字。""")

        user_msg = HumanMessage(content=f"""目标人物：{request.target_person}
补充背景：{request.background_info or "无"}
当前聊天内容：
{chat_context}

请按照以上步骤进行分析，最终以 JSON 格式直接输出结果。""")

        result = await agent_executor.ainvoke({"messages": [sys_msg, user_msg]})
        raw_output = result["messages"][-1].content

        # 尝试从输出中提取 JSON（LLM 可能包裹在 ```json...``` 中）
        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0]
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0]

        return EmotionResponse.model_validate_json(raw_output.strip())

    except Exception as e:
        import traceback
        print(f"Error in emotion skill: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"情感分析执行失败: {str(e)}")
