import streamlit as st
import requests

# 配置后端 FastAPI 的基础地址
BASE_URL = "http://127.0.0.1:8000/api/v1"

# 设置页面基本属性
st.set_page_config(page_title="聊天记录分析 Agent", layout="wide")

# ==========================================
# UI 界面：侧边栏配置
# ==========================================
with st.sidebar:
    st.header("⚙️ 参数配置")
    target_person = st.text_input("分析目标对象 (如: 张三)", value="张三")
    background_info = st.text_area("补充背景信息 (选填，用于弦外之音分析)",
                                   placeholder="例如：最近他刚换了工作，压力比较大...")

# ==========================================
# UI 界面：主展示区
# ==========================================
st.title("💬 微信/QQ 聊天记录深度分析引擎")
st.write("请输入聊天记录")

# 输入聊天记录
chat_input = st.text_area("近期聊天记录", height=150,
                          placeholder="[张三 10:00]: 你今天怎么没理我？\n[我 10:05]: 在忙项目。")

# 将四个功能按键并排显示
col1, col2, col3, col4 = st.columns(4)

# 辅助函数：构造请求数据
def build_payload():
    # 这里为了演示，我们先简单地将纯文本作为最新一条消息发送
    # 后续我们可以引入更复杂的文本解析逻辑
    return {
        "target_person": target_person,
        "recent_chat": [{"sender": target_person, "content": chat_input, "timestamp": "now"}],
        "background_info": background_info
    }

# ==========================================
# 按键逻辑处理
# ==========================================
with col1:
    if st.button("🎭 模仿聊天对象", use_container_width=True):
        if chat_input:
            with st.spinner("Agent 正在思考中..."):
                response = requests.post(f"{BASE_URL}/imitate", json=build_payload())
                if response.status_code == 200:
                    st.success("分析完成！")
                    st.info(f"**模拟回复：** {response.json().get('reply')}")
                else:
                    st.error("后端连接失败，请检查 FastAPI 服务。")
        else:
            st.warning("请先输入聊天记录。")

with col2:
    if st.button("❤️ 历史情感分析", use_container_width=True):
        if chat_input:
            with st.spinner("Agent 正在提取情感特征..."):
                response = requests.post(f"{BASE_URL}/emotion_analyze", json=build_payload())
                if response.status_code == 200:
                    data = response.json()
                    st.success("分析完成！")
                    st.metric(label="情感烈度分数", value=f"{data.get('emotion_score')}/100")
                    st.write(f"**主导情绪：** {data.get('dominant_emotion')}")
                    st.write(f"**分析依据：** {data.get('analysis_reasoning')}")
                else:
                    st.error("后端连接失败。")
        else:
            st.warning("请先输入聊天记录。")

with col3:
    if st.button("🔮 预测对话走向", use_container_width=True):
        if chat_input:
            with st.spinner("Agent 正在推演未来走向..."):
                response = requests.post(f"{BASE_URL}/predict_trend", json=build_payload())
                if response.status_code == 200:
                    st.success("推演完成！")
                    predictions = response.json().get('predictions', [])
                    for i, pred in enumerate(predictions):
                        st.write(f"{i + 1}. {pred}")
                else:
                    st.error("后端连接失败。")
        else:
            st.warning("请先输入聊天记录。")

with col4:
    if st.button("🕵️ 洞察弦外之音", use_container_width=True):
        if chat_input:
            with st.spinner("Agent 正在结合 RAG 知识库深度解码..."):
                response = requests.post(f"{BASE_URL}/read_between_lines", json=build_payload())
                if response.status_code == 200:
                    st.success("解码完成！")
                    st.write(f"**潜台词分析：** {response.json().get('hidden_meaning')}")
                else:
                    st.error("后端连接失败。")
        else:
            st.warning("请先输入聊天记录。")