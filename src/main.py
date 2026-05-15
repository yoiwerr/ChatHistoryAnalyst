from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel,Field
from typing import List, Optional
import re
import os
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

#初始化agent
load_dotenv()
base_url = os.getenv("DASHSCOPE_BASE_URL")
api_key = os.getenv("DASHSCOPE_API_KEY")

model_q = init_chat_model(
    model = "qwen3-max",
    model_provider = "openai",
    base_url = base_url,
    api_key = api_key
)
tools = []
agent = create_agent(
    model = model_q,
    checkpointer = MemorySaver(),
    tools = tools
)
# 初始化 FastAPI 实例
app = FastAPI(title="Chat Analysis Agent API", version="1.0")

# ==========================================
# 1. 定义数据结构 (Schemas)
# 使用 Pydantic 确保前后端数据交互的严格性
# ==========================================

class ChatMessage(BaseModel):
    sender: str = Field(..., description="发送者名称")
    content: str = Field(..., description="文本内容")
    timestamp: str = Field(..., description="时间戳")

class AnalysisRequest(BaseModel):
    target_person: str = Field(..., description="目标分析对象名称")
    recent_chat: List[ChatMessage] = Field(..., description="近期的聊天记录列表")
    background_info: Optional[str] = Field(default=None, description="可选的补充背景信息")

class EmotionResponse(BaseModel):
    emotion_score: int          # 情感分数 1-100
    dominant_emotion: str       # 主导情绪
    analysis_reasoning: str     # 分析依据


# ==========================================
# 新增：数据导入结构定义
# ==========================================
class ImportRequest(BaseModel):
    format_type: str = Field(description="数据格式，必须是 'text' 或 'json'")
    # 当 format_type 为 'text' 时读取此字段
    text_data: Optional[str] = None
    # 当 format_type 为 'json' 时读取此字段，期望是一个字典列表
    json_data: Optional[List[dict]] = None


# ==========================================
# 新增：聊天数据导入接口
# ==========================================
@app.post("/api/v1/import_chat", tags=["Data Processing"])
async def import_chat_data(request: ImportRequest):
    """
    数据接入层：支持纯文本解析和 JSON 直接导入，统一格式化为标准数据流。
    """
    parsed_chats: List[ChatMessage] = []

    # 分支一：处理 JSON 格式
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

    # 分支二：处理纯文本格式
    elif request.format_type == "text" and request.text_data:
        # 设定纯文本的正则匹配模式，假设格式为 "[发送者 时间]: 内容"
        # 例如: "[张三 10:05]: 你好啊"
        pattern = r"\[(.*?)\s+(.*?)\]:\s*(.*)"

        for line in request.text_data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue  # 跳过空行

            match = re.match(pattern, line)
            if match:
                sender, time, content = match.groups()
                parsed_chats.append(ChatMessage(
                    sender=sender,
                    timestamp=time,
                    content=content
                ))
            else:
                # 记录无法解析的行，真实业务中可以写入日志
                print(f"Warning: 无法解析文本行 -> {line}")

    else:
        raise HTTPException(status_code=400, detail="缺少数据，或者 format_type 未知。")

    # ----------------------------------------------------
    # TODO: 在这里，你可以将 parsed_chats 存入 Redis 或 Chroma 向量数据库
    # ----------------------------------------------------

    return {
        "status": "success",
        "message": f"成功导入 {len(parsed_chats)} 条聊天记录。",
        "data": parsed_chats  # 返回解析后的标准格式供你确认
    }

# ==========================================
# 2. 定义 API 接口 (Endpoints)
# ==========================================

# ==========================================
# 2. 定义 API 接口 (Endpoints)
# ==========================================

@app.post("/api/v1/imitate", tags=["Skills"])
async def skill_imitate(request: AnalysisRequest):
    """
    Skill 1: 模仿聊天对象对话
    """
    recent_chat = request.recent_chat
    target_person = request.target_person

    # 1. 前置校验：聊天记录不能为空
    if not recent_chat:
        raise HTTPException(status_code=400, detail="聊天记录不能为空")

    # 2. 提取目标人物的历史发言（作为 Few-shot 样本）
    target_utterances = [
        msg.content for msg in recent_chat
        if msg.sender == target_person
    ]

    if not target_utterances:
        raise HTTPException(status_code=400,
                            detail=f"聊天记录中未找到目标人物 '{target_person}' 的发言，无法提取模仿样本")

    # 将历史发言拼接成清晰的文本列表
    few_shot_text = "\n".join([f"- {text}" for text in target_utterances])

    # 3. 寻找触发句：倒序遍历寻找最后一条非目标人物的发言
    trigger_message = ""
    for msg in reversed(recent_chat):
        if msg.sender != target_person:
            trigger_message = msg.content
            break

    if not trigger_message:
        raise HTTPException(status_code=400, detail="未找到非目标人物的发言，无法触发回复")

    # 4. LangChain 核心链路设计
    # 构建 System Prompt，明确角色要求并注入样本
    system_prompt = (
        "你是一个高级社交模仿专家。你的任务是深度模仿目标人物的聊天风格，包括说话语气、口癖、标点符号习惯以及句子长度。\n"
        "请仔细分析以下目标人物（{target_person}）的历史发言样本，学习其风格：\n"
        "<samples>\n"
        "{few_shot_text}\n"
        "</samples>\n\n"
        "参考背景信息：{background_info}\n\n"
        "要求：请严格以目标人物的口吻回复用户的最新一句话。只输出模仿的回复内容本身，不要包含任何多余的解释、前缀或格式。"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{trigger_message}")
    ])

    # 将 Prompt 和大模型通过管道符组合成 Chain
    # 注意：这里直接使用你全局初始化的 model_q
    chain = prompt_template | model_q

    # 5. 执行 LLM 调用并返回
    try:
        response = await chain.ainvoke({
            "target_person": target_person,
            "few_shot_text": few_shot_text,
            "background_info": request.background_info or "无特殊背景",
            "trigger_message": trigger_message
        })

        return {
            "status": "success",
            "reply": response.content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"大模型生成失败: {str(e)}")
@app.post("/api/v1/emotion_analyze", response_model=EmotionResponse, tags=["Skills"])
async def skill_emotion(request: AnalysisRequest):
    """
    Skill 2: 历史情感分析 (强制结构化输出)
    """
    # 伪代码逻辑：
    # 1. 组装 recent_chat 为长文本
    # 2. 调用 LLM 并使用 LangChain 的 with_structured_output(EmotionResponse)
    # 3. 解析结果并返回
    return EmotionResponse(
        emotion_score=85,
        dominant_emotion="焦虑并带有期待",
        analysis_reasoning="用户多次使用了反问句，并且回复时间间隔极短..."
    )

@app.post("/api/v1/predict_trend", tags=["Skills"])
async def skill_predict(request: AnalysisRequest):
    """
    Skill 3: 猜测最新对话走向
    """
    # 需要提取 Redis 中的近期上下文，推演未来走向
    return {"predictions": ["走向A: 激烈争吵", "走向B: 妥协让步"]}

@app.post("/api/v1/read_between_lines", tags=["Skills"])
async def skill_hidden_meaning(request: AnalysisRequest):
    """
    Skill 4: 弦外之音分析 (RAG 增强)
    """
    # 伪代码逻辑：
    # 1. 从心理学 RAG 数据库检索相关理论
    # 2. 结合 request.background_info 
    # 3. 由 LLM 综合输出分析报告
    return {"hidden_meaning": "表面上在拒绝，但实际上是在测试你的态度..."}

# 启动服务器的入口
if __name__ == "__main__":
    import uvicorn
    # 推荐使用这种方式在开发阶段热重载代码
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)