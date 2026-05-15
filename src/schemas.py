# src/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional


class ChatMessage(BaseModel):
    sender: str = Field(..., description="发送者名称")
    content: str = Field(..., description="文本内容")
    timestamp: str = Field(..., description="时间戳")


class AnalysisRequest(BaseModel):
    target_person: str = Field(..., description="目标分析对象名称")
    recent_chat: List[ChatMessage] = Field(..., description="近期的聊天记录列表")
    background_info: Optional[str] = Field(default=None, description="可选的补充背景信息")


class ImportRequest(BaseModel):
    format_type: str = Field(description="数据格式，必须是 'text' 或 'json'")
    text_data: Optional[str] = None
    json_data: Optional[List[dict]] = None

class EmotionResponse(BaseModel):
    """
    Skill 2: 情感分析的强制结构化输出规范
    大模型将严格按照此结构返回数据
    """
    emotion_score: int = Field(
        ...,
        description="情感得分，范围 0-100。0代表极其消极/愤怒，50代表中立，100代表极其积极/开心"
    )
    dominant_emotion: str = Field(
        ...,
        description="主导情感标签，例如：'焦虑'、'开心'、'冷漠'、'试探' 等，精简为几个字"
    )
    analysis_reasoning: str = Field(
        ...,
        description="基于聊天记录的详细分析推导过程，解释为什么给出上述得分和标签"
    )
# 如果你后续做 Skill 2，可以在这里继续添加 EmotionResponse