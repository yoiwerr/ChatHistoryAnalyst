from fastapi import FastAPI, HTTPException
import re
from typing import List, Optional
from src.schemas import ImportRequest, AnalysisRequest, ChatMessage, EmotionResponse, AtmosphereResponse
from src.skills.skill01_imitate import execute_imitate_skill
from src.skills.skill02_emotion import execute_emotion_skill
from src.skills.skill03_atmosphere import execute_atmosphere_skill
from src.rag_function import save_chats_to_long_term_memory

app = FastAPI(title="Chat Analysis Agent API", version="1.0")
@app.post("/api/v1/import_chat", tags=["Data Processing"])
async def import_chat_data(request: ImportRequest):
    """
    数据接入层：解析聊天记录并自动存入 RAG 向量库。
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

    # 自动存入 RAG 向量库
    rag_message = ""
    if parsed_chats:
        try:
            rag_message = save_chats_to_long_term_memory(
                recent_chats=parsed_chats,
                target_person=request.target_person
            )
        except Exception as e:
            print(f"RAG 写入失败: {e}")

    return {
        "status": "success",
        "message": f"成功导入 {len(parsed_chats)} 条聊天记录。{rag_message}",
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

@app.post("/api/v1/analyze_atmosphere", response_model=AtmosphereResponse, tags=["Skills"])
async def skill_atmosphere(request: AnalysisRequest):
    """
    Skill 3: 聊天气氛分析与沟通建议 (Demo版)
    """
    result = await execute_atmosphere_skill(request)
    return result


@app.post("/api/v1/add_memory", tags=["Memory Management"])
async def add_chat_memory(request: AnalysisRequest):
    """
    数据沉淀接口：将前端的聊天记录写入 PostgreSQL 向量库，形成长期记忆。
    """
    try:
        # 调用 rag_function.py 中的核心逻辑
        result_message = save_chats_to_long_term_memory(
            recent_chats=request.recent_chat,
            target_person=request.target_person
        )
        return {
            "status": "success",
            "message": result_message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存记忆失败: {str(e)}")

# # 你可以先预留其他技能的空路由
# @app.post("/api/v1/emotion_analyze", tags=["Skills"])
# async def skill_emotion(request: AnalysisRequest):
#     pass