# src/skills/skill_3_atmosphere.py
from fastapi import HTTPException
from langchain_core.prompts import ChatPromptTemplate
from src.schemas import AnalysisRequest, AtmosphereResponse
from src.core_llm import llm


async def execute_atmosphere_skill(request: AnalysisRequest) -> AtmosphereResponse:
    """
    执行 Skill 3: 聊天气氛分析与沟通建议的 Demo 业务逻辑
    """
    recent_chat = request.recent_chat

    # 1. 基础数据校验
    if not recent_chat:
        raise HTTPException(status_code=400, detail="聊天记录不能为空")

    # 2. 将聊天记录格式化为直观的对话剧本格式
    chat_transcript = "\n".join(
        [f"[{msg.timestamp}] {msg.sender}: {msg.content}" for msg in recent_chat]
    )

    # 3. 构建 LangChain Prompt 模板
    # 设计思路：在此处重点强调对“迎合”、“软弱”等姿态的捕捉
    system_prompt = (
        "你是一位深谙人际交往、权力博弈和沟通心理学的专家顾问。\n"
        "请阅读以下的聊天记录，系统性地分析当前的聊天气氛和双方的权力动态（Power Dynamic）。\n"
        "你需要特别关注并敏锐地指出：是否有一方在沟通中表现得【太软弱】、【太迎合】、【过度讨好】或【丧失主导权】。\n\n"
        "背景信息参考：{background_info}\n\n"
        "聊天记录如下：\n"
        "<chat_history>\n"
        "{chat_transcript}\n"
        "</chat_history>\n\n"
        "请保持客观、一针见血，并给出具有实操性的行动建议，帮助处于劣势的一方不卑不亢地找回沟通节奏。"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "请开始分析当前的聊天气氛并给出具体的沟通建议。")
    ])

    # 4. 绑定结构化输出拦截器
    structured_llm = llm.with_structured_output(AtmosphereResponse)

    # 组装 Chain
    chain = prompt_template | structured_llm

    # 5. 异步调用大模型
    try:
        # 注意：这里我们传入了 chat_transcript 和 background_info
        response: AtmosphereResponse = await chain.ainvoke({
            "background_info": request.background_info or "无特殊背景",
            "chat_transcript": chat_transcript
        })
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"气氛分析大模型调用失败: {str(e)}")