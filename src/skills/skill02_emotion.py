# src/skills/skill_2_emotion.py
from fastapi import HTTPException
from langchain_core.prompts import ChatPromptTemplate
from src.schemas import AnalysisRequest, EmotionResponse
from src.core_llm import llm


async def execute_emotion_skill(request: AnalysisRequest) -> EmotionResponse:
    """
    执行 Skill 2: 历史情感分析的具体业务逻辑
    """
    recent_chat = request.recent_chat
    target_person = request.target_person

    # 1. 基础数据校验
    if not recent_chat:
        raise HTTPException(status_code=400, detail="聊天记录不能为空")

    # 2. 将聊天记录格式化为易于大模型理解的对话剧本格式
    # 例如:
    # [10:00] 张三: 在吗？
    # [10:01] 李四: 怎么了？
    chat_transcript = "\n".join(
        [f"[{msg.timestamp}] {msg.sender}: {msg.content}" for msg in recent_chat]
    )

    # 3. 构建 LangChain Prompt 模板
    system_prompt = (
        "你是一位资深的心理学与沟通分析专家。\n"
        "请阅读以下提供的近期聊天记录上下文，并重点分析【{target_person}】在这段对话中展现出的心理状态和情感。\n"
        "背景信息参考：{background_info}\n\n"
        "聊天记录如下：\n"
        "<chat_history>\n"
        "{chat_transcript}\n"
        "</chat_history>\n\n"
        "请严格根据聊天内容中的语气、用词、回复频率等细节，客观推导 {target_person} 的情感状态。"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "请开始分析 {target_person} 的情感。")
    ])

    # 4. 绑定结构化输出！这是 LangChain 的魔法所在
    # 这会强制大模型返回符合 EmotionResponse Pydantic 规范的 Python 对象
    structured_llm = llm.with_structured_output(EmotionResponse)

    # 组装 Chain
    chain = prompt_template | structured_llm

    # 5. 异步调用并返回结构化对象
    try:
        response: EmotionResponse = await chain.ainvoke({
            "target_person": target_person,
            "background_info": request.background_info or "无",
            "chat_transcript": chat_transcript
        })

        # 因为返回的 response 已经是 EmotionResponse 对象了，我们直接返回即可
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"情感分析模型调用失败，可能是格式化解析异常: {str(e)}")