# src/skills/skill_1_imitate.py
from fastapi import HTTPException
from langchain_core.prompts import ChatPromptTemplate
from src.schemas import AnalysisRequest
from src.core_llm import llm


async def execute_imitate_skill(request: AnalysisRequest) -> dict:
    """
    执行 Skill 1: 模仿聊天对象的具体业务逻辑
    """
    recent_chat = request.recent_chat
    target_person = request.target_person

    # 1. 基础数据校验
    if not recent_chat:
        raise HTTPException(status_code=400, detail="聊天记录不能为空")

    chat_transcript = "\n".join(
        [f"[{msg.sender}:{msg.timestamp}]：{msg.content}" for msg in recent_chat if msg.sender == target_person]
    )

    # 2. 构建语料样本 (Few-shot)
    # target_utterances = [msg.content for msg in recent_chat if msg.sender == target_person]

    if not chat_transcript:
        raise HTTPException(status_code=400, detail=f"聊天记录中未找到目标人物 '{target_person}' 的发言。")

    # # 将历史发言用清晰的列表格式拼接
    # few_shot_text = "\n".join([f"- {text}" for text in target_utterances])

    # 3. 提取触发句 (寻找最后一条非目标人物的发言)
    trigger_message = ""
    for msg in reversed(recent_chat):
        if msg.sender != target_person:
            trigger_message = msg.content
            break

    if not trigger_message:
        raise HTTPException(status_code=400, detail="未找到非目标人物的发言，无法触发回复")

    # 4. 构建 LangChain Prompt 模板
    # 设计思路：使用明确的 XML 标签 <samples> 隔离样本区，防止大模型产生幻觉
    system_prompt = (
        "你是一个高级社交模仿专家。你的任务是深度模仿目标人物的聊天风格，"
        "包括说话语气、口癖、标点符号习惯以及句子长度。\n"
        "请仔细分析以下目标人物（{target_person}）的历史发言样本，学习其风格：\n"
        "<samples>\n"
        "{few_shot_text}\n"
        "</samples>\n\n"
        "参考背景信息：{background_info}\n\n"
        "要求：请严格以目标人物的口吻回复用户的最新一句话。"
        "只输出模仿的回复内容本身，绝对不要包含任何多余的解释、前缀（如'某某说：'）或格式。"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{trigger_message}")
    ])

    # 将 Prompt 和大模型通过 LangChain 表达式语言 (LCEL) 组合成链
    chain = prompt_template | llm

    # 5. 异步调用大模型并处理异常
    try:
        response = await chain.ainvoke({
            "target_person": target_person,
            "few_shot_text": chat_transcript,
            "background_info": request.background_info or "无特殊背景",
            "trigger_message": trigger_message
        })

        return {"status": "success", "reply": response.content}
    except Exception as e:
        # 捕捉模型调用可能产生的网络超时或鉴权错误
        raise HTTPException(status_code=500, detail=f"大模型生成失败: {str(e)}")