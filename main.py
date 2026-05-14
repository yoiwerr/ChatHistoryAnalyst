from fastapi import FastAPI, HTTPException
from pydantic import BaseModel,Field
from typing import List, Optional
import re

# 初始化 FastAPI 实例
app = FastAPI(title="Chat Analysis Agent API", version="1.0")

# ==========================================
# 1. 定义数据结构 (Schemas)
# 使用 Pydantic 确保前后端数据交互的严格性
# ==========================================

class ChatMessage(BaseModel):
    sender: str
    content: str
    timestamp: str

class AnalysisRequest(BaseModel):
    target_person: str
    recent_chat: List[ChatMessage]
    background_info: Optional[str] = None # 用于 Skill 4 的额外背景

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

@app.post("/api/v1/imitate", tags=["Skills"])
async def skill_imitate(request: AnalysisRequest):
    """
    Skill 1: 模仿聊天对象对话
    """
    # 伪代码逻辑：
    # 1. query = request.recent_chat[-1].content
    # 2. few_shots = vector_db.search(query, filter={"sender": request.target_person})
    # 3. response = llm.invoke(prompt_with_few_shots)
    return {"status": "success", "reply": "这是模仿生成的回复内容"}

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