from fastapi import FastAPI, HTTPException
import re
from typing import List, Optional
from src.schemas import ImportRequest, AnalysisRequest, ChatMessage
from src.core_llm import llm
from langchain_core.prompts import ChatPromptTemplate
from fastapi import FastAPI, HTTPException
import re
from src.schemas import ImportRequest, AnalysisRequest, ChatMessage, EmotionResponse
from src.skills.skill02_emotion import execute_emotion_skill
from src.skills.skill01_imitate import execute_imitate_skill

app = FastAPI(title="Chat Analysis Agent API", version="1.0")
@app.post("/api/v1/import_chat", tags=["Data Processing"])
async def import_chat_data(request: ImportRequest):
    """
    数据接入层：支持纯文本解析和 JSON 直接导入，统一格式化为标准数据流。
    """
    parsed_chats: List[ChatMessage] = []

    if request.format_type == "json" and request.json_data:
        try:
            for item in request.json_data:
                parsed_chats.append(ChatMessage(
                    sender=item.get("sender", "Unknown"),
                    content=item.get("content", ""),
                    timestamp=item.get("timestamp", "Unknown")
                ))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败: {str(e)}")

    elif request.format_type == "text" and request.text_data:
        pattern = r"\[(.*?)\s+(.*?)\]:\s*(.*)"
        for line in request.text_data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            match = re.match(pattern, line)
            if match:
                sender, time, content = match.groups()
                parsed_chats.append(ChatMessage(sender=sender, timestamp=time, content=content))
            else:
                print(f"Warning: 无法解析文本行 -> {line}")
    else:
        raise HTTPException(status_code=400, detail="缺少数据，或者 format_type 未知。")

    return {
        "status": "success",
        "message": f"成功导入 {len(parsed_chats)} 条聊天记录。",
        "data": parsed_chats
    }


@app.post("/api/v1/imitate", tags=["Skills"])
async def skill_imitate(request: AnalysisRequest):
    """
    Skill 1: 模仿聊天对象对话
    所有的核心业务逻辑均已解耦至 src/skills/skill_1_imitate.py
    """
    # 直接调用封装好的技能函数
    result = await execute_imitate_skill(request)
    return result


@app.post("/api/v1/emotion_analyze", response_model=EmotionResponse, tags=["Skills"])
async def skill_emotion(request: AnalysisRequest):
    """
    Skill 2: 历史情感分析 (强制结构化输出)
    """
    # 直接调用封装好的技能函数
    result = await execute_emotion_skill(request)
    return result

# 你可以先预留其他技能的空路由
@app.post("/api/v1/emotion_analyze", tags=["Skills"])
async def skill_emotion(request: AnalysisRequest):
    pass