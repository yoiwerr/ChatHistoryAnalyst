import streamlit as st
import requests
import re

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
    parsed_chats = []

    # 使用正则解析输入的聊天记录格式: [发送者 时间]: 内容
    pattern = r"\[(.*?)\s+(.*?)\]:\s*(.*)"

    # 逐行解析文本框的内容
    for line in chat_input.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line)
        if match:
            sender, time, content = match.groups()
            parsed_chats.append({
                "sender": sender,
                "content": content,
                "timestamp": time
            })

    # 兼容处理：如果用户没有按标准格式输入，就默认将全部文本视为“我”发给 Agent 的单条消息
    if not parsed_chats:
        parsed_chats = [{
            "sender": "我",
            "content": chat_input,
            "timestamp": "now"
        }]

    return {
        "target_person": target_person,
        "recent_chat": parsed_chats,
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
                    # 核心修改：打印出真实的错误码和后端返回的详细报错信息
                    st.error(f"请求失败！HTTP 状态码: {response.status_code}")
                    st.code(response.text)
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
                    # 核心修改：打印出真实的错误码和后端返回的详细报错信息
                    st.error(f"请求失败！HTTP 状态码: {response.status_code}")
                    st.code(response.text)
        else:
            st.warning("请先输入聊天记录。")

with col3:
    if st.button("🔮 气氛分析", use_container_width=True):
        if chat_input:
            # 1. 更新加载提示语
            with st.spinner("Agent 正在深度解析聊天气氛与权力动态..."):

                # 2. 确保请求路径完整，拼接上 /api/v1/
                target_url = f"{BASE_URL}/analyze_atmosphere"
                response = requests.post(target_url, json=build_payload())

                if response.status_code == 200:
                    st.success("气氛分析完成！")

                    # 3. 解析后端返回的新 JSON 数据结构
                    result = response.json()
                    summary = result.get('atmosphere_summary', '无总结数据')
                    power = result.get('power_dynamic', '无权力动态数据')
                    suggestions = result.get('actionable_suggestions', [])

                    # 4. 使用 Streamlit 组件优雅地展示这些数据
                    st.markdown("### 📊 气氛整体总结")
                    st.info(summary)  # 使用 info 组件高亮显示总结

                    st.markdown("### ⚖️ 权力动态剖析")
                    st.write(power)

                    st.markdown("### 💡 具体行动建议")
                    if suggestions:
                        for i, advice in enumerate(suggestions):
                            # 使用 markdown 渲染带有编号的建议，视觉效果更好
                            st.markdown(f"**{i + 1}.** {advice}")
                    else:
                        st.write("暂无具体建议。")

                else:
                    st.error(f"请求失败！HTTP 状态码: {response.status_code}")
                    st.code(response.text)
        else:
            st.warning("请先输入聊天记录。")
