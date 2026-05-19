import streamlit as st
import requests
import re

BASE_URL = "http://127.0.0.1:8000/api/v1"

# ── 页面配置 ──────────────────────────────────
st.set_page_config(
    page_title="ChatLab — 聊天记录分析引擎",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 全局样式 ──────────────────────────────────
st.markdown("""
<style>
    /* 主容器留白 */
    .block-container { padding-top: 1.5rem; }
    /* 卡片容器 */
    .card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        background: #fafafa;
    }
    /* 结果指标数字 */
    .big-number {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a73e8;
    }
    /* 标签 */
    .tag {
        display: inline-block;
        padding: 0.2rem 0.8rem;
        border-radius: 99px;
        font-size: 0.8rem;
        font-weight: 500;
        background: #e8f0fe;
        color: #1a73e8;
        margin-right: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

# ── 会话状态初始化 ──────────────────────────────
DEFAULTS = {
    "parsed_chats": [],
    "upload_message": "",
    "upload_error": None,
    "last_file_key": None,
    "manual_input": "",
    "result_tab": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ═══════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/chat.png", width=48)
    st.title("ChatLab")

    st.markdown("---")

    # ── 分析配置 ──
    st.subheader("⚙️ 分析配置")
    target_person = st.text_input(
        "目标对象",
        value="雷翼逐云",
        placeholder="输入对方昵称",
        label_visibility="collapsed",
    )
    background_info = st.text_area(
        "补充背景",
        placeholder="选填：它是渣男",
        height=80,
        label_visibility="collapsed",
    )
    save_rag = st.checkbox("存入长期记忆库", value=False)

    st.markdown("---")

    # ── 分析入口 ──
    st.subheader("🔍 开始分析")

    def _call_skill(endpoint: str, payload: dict, label: str) -> dict | None:
        """通用技能调用，返回 JSON 或 None。"""
        try:
            resp = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=120)
        except requests.ConnectionError:
            st.error("无法连接后端，请确认服务已启动：`uvicorn src.main:app`")
            return None
        if resp.status_code != 200:
            st.error(f"请求失败 HTTP {resp.status_code}")
            st.code(resp.text[:500])
            return None
        return resp.json()

    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button("🎭 模仿", use_container_width=True, help="模仿对方的语气和风格回复"):
            st.session_state.result_tab = "imitate"
    with btn_col2:
        if st.button("❤️ 情感", use_container_width=True, help="分析对方的历史情感状态"):
            st.session_state.result_tab = "emotion"
    with btn_col3:
        if st.button("🔮 气氛", use_container_width=True, help="分析对话的权力动态和沟通建议"):
            st.session_state.result_tab = "atmosphere"

    st.markdown("---")

    # ── 状态指示 ──
    chat_count = len(st.session_state.get("parsed_chats", []))
    status_color = "#34a853" if chat_count > 0 else "#9aa0a6"
    st.markdown(
        f"""
        <div style="font-size:0.8rem;color:#5f6368;">
            当前数据 &nbsp;
            <span style="color:{status_color};font-weight:600;">{chat_count}</span>
            &nbsp; 条消息
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.caption("ChatLab v0.1 · 基于AI大模型 · 数据仅本地存储")


# ═══════════════════════════════════════════════════
# 主区域
# ═══════════════════════════════════════════════════

# ── Hero ──
st.markdown("""
<div style="margin-bottom:0.5rem;">
    <h1 style="margin-bottom:0.2rem;">聊天记录深度分析</h1>
    <p style="color:#5f6368;font-size:1rem;">
        上传聊天截图或文本文件，AI 自动解析并分析情感、气氛与沟通姿态
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── 第一行：上传区 + 预览区 ──
left, right = st.columns([5, 4], gap="medium")

with left:
    st.subheader("📤 导入聊天记录")

    upload_tab, manual_tab = st.tabs(["📎 文件上传", "✏️ 手动输入"])

    with upload_tab:
        uploaded_file = st.file_uploader(
            "拖拽文件到此处，或点击选择",
            type=["txt", "json", "png", "jpg", "jpeg", "webp"],
            key="chat_file_uploader",
            label_visibility="collapsed",
        )
        st.caption("支持 TXT · JSON · PNG · JPG · WebP（截图自动 OCR）")

        if uploaded_file is not None:
            file_key = f"{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.last_file_key != file_key:
                st.session_state.last_file_key = file_key
                with st.spinner("正在解析文件…"):
                    try:
                        resp = requests.post(
                            f"{BASE_URL}/upload_chat_file",
                            files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                            data={
                                "target_person": target_person,
                                "save_to_rag": str(save_rag).lower(),
                            },
                            timeout=180,
                        )
                    except requests.ConnectionError:
                        st.session_state.upload_error = "无法连接后端服务"
                        st.session_state.parsed_chats = []
                        st.session_state.upload_message = ""
                    else:
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.parsed_chats = data.get("parsed_chats", [])
                            st.session_state.upload_message = data.get("message", "")
                            st.session_state.upload_error = None
                        else:
                            st.session_state.parsed_chats = []
                            st.session_state.upload_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                            st.session_state.upload_message = ""
                st.rerun()

        # 展示上传反馈
        if st.session_state.upload_error:
            st.error(st.session_state.upload_error)
        elif st.session_state.upload_message and st.session_state.parsed_chats:
            st.success(st.session_state.upload_message)

    with manual_tab:
        manual_input = st.text_area(
            "按格式粘贴聊天记录",
            value=st.session_state.manual_input,
            height=140,
            placeholder="[张三 10:00]: 你今天怎么没理我？\n[我 10:05]: 在忙项目。",
            key="widget_manual_input",
            label_visibility="collapsed",
        )
        st.session_state.manual_input = manual_input
        st.caption("格式：`[昵称 时间]: 消息内容`，每行一条")

with right:
    st.subheader("📋 消息预览")

    chats = st.session_state.get("parsed_chats", [])

    # 兜底：文件无数据时，尝试解析手动输入
    if not chats and st.session_state.get("manual_input", "").strip():
        pattern = r"\[(.*?)\s+(.*?)\][:：]\s*(.*)"
        for line in st.session_state.manual_input.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(pattern, line)
            if m:
                sender, time, content = m.groups()
                chats.append({"sender": sender, "content": content, "timestamp": time})

    if chats:
        with st.container(height=280):
            for i, chat in enumerate(chats):
                is_me = "我" in chat.get("sender", "")
                align = "flex-end" if is_me else "flex-start"
                bubble_color = "#e3f2fd" if is_me else "#f5f5f5"
                text_align = "right" if is_me else "left"
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:{align};margin-bottom:0.4rem;">
                        <div style="max-width:80%;padding:0.4rem 0.8rem;
                                    border-radius:12px;background:{bubble_color};
                                    text-align:{text_align};font-size:0.85rem;">
                            <div style="font-weight:600;font-size:0.7rem;color:#5f6368;">
                                {chat.get('sender','?')} · {chat.get('timestamp','')}
                            </div>
                            {chat.get('content','')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("上传文件或手动输入后，解析结果会出现在这里", icon="👆")

# ── 分隔线 ──
st.markdown("---")


# ═══════════════════════════════════════════════════
# 结果展示区
# ═══════════════════════════════════════════════════

def _get_chats():
    """组装当前可用的聊天数据。"""
    result = list(st.session_state.get("parsed_chats", []))
    if not result and st.session_state.get("manual_input", "").strip():
        pattern = r"\[(.*?)\s+(.*?)\][:：]\s*(.*)"
        for line in st.session_state.manual_input.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(pattern, line)
            if m:
                sender, time, content = m.groups()
                result.append({"sender": sender, "content": content, "timestamp": time})
    return result


def _build_payload():
    return {
        "target_person": target_person,
        "recent_chat": _get_chats(),
        "background_info": background_info or None,
    }


tab = st.session_state.get("result_tab")

if tab is None:
    st.markdown(
        """
        <div style="text-align:center;padding:2rem 0;color:#9aa0a6;">
            <p style="font-size:1.1rem;">👈 从侧边栏选择分析类型，或上传文件后点击上方标签导入数据</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

elif tab == "imitate":
    st.subheader("🎭 模仿对方回复")
    chats = _get_chats()
    if not chats:
        st.warning("请先导入聊天记录")
    else:
        with st.spinner("Agent 正在模仿语气…"):
            data = _call_skill("imitate", _build_payload(), "模仿")
        if data:
            st.markdown("### 对方可能会这样回复")
            st.info(data.get("reply", "—"))
            st.caption("以上回复由 AI 生成，仅供娱乐参考")

elif tab == "emotion":
    st.subheader("❤️ 历史情感分析")
    chats = _get_chats()
    if not chats:
        st.warning("请先导入聊天记录")
    else:
        with st.spinner("Agent 正在提取情感特征…"):
            data = _call_skill("emotion_analyze", _build_payload(), "情感分析")
        if data:
            score = data.get("emotion_score", 0)
            # 情绪颜色映射
            if score >= 70:
                color = "#34a853"
                emoji = "😊"
            elif score >= 40:
                color = "#fbbc04"
                emoji = "😐"
            else:
                color = "#ea4335"
                emoji = "😞"

            m1, m2, m3 = st.columns([1, 1, 2])
            with m1:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:1rem;">
                        <div style="font-size:0.8rem;color:#5f6368;">情感指数</div>
                        <div class="big-number" style="color:{color};">{score}<span style="font-size:1rem;">/100</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:1rem;">
                        <div style="font-size:0.8rem;color:#5f6368;">主导情绪</div>
                        <div style="font-size:1.5rem;margin-top:0.5rem;">{emoji}</div>
                        <span class="tag">{data.get('dominant_emotion', '—')}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown("**分析依据**")
                st.write(data.get("analysis_reasoning", "—"))

elif tab == "atmosphere":
    st.subheader("🔮 气氛与权力动态分析")
    chats = _get_chats()
    if not chats:
        st.warning("请先导入聊天记录")
    else:
        with st.spinner("Agent 正在深度解析…"):
            data = _call_skill("analyze_atmosphere", _build_payload(), "气氛分析")
        if data:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### 📊 气氛总结")
                st.info(data.get("atmosphere_summary", "—"))
            with col_b:
                st.markdown("#### ⚖️ 权力动态")
                st.write(data.get("power_dynamic", "—"))

            st.markdown("#### 💡 行动建议")
            suggestions = data.get("actionable_suggestions", [])
            if suggestions:
                for i, s in enumerate(suggestions):
                    st.markdown(
                        f"""
                        <div style="display:flex;align-items:baseline;margin-bottom:0.5rem;">
                            <span style="
                                display:inline-flex;align-items:center;justify-content:center;
                                width:24px;height:24px;border-radius:50%;
                                background:#1a73e8;color:white;font-size:0.75rem;font-weight:600;
                                margin-right:0.6rem;flex-shrink:0;
                            ">{i + 1}</span>
                            <span>{s}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.write("暂无建议。")

# ── 重置按钮 ──
if tab is not None:
    st.markdown("---")
    if st.button("🔄 清空结果，重新开始", use_container_width=False):
        st.session_state.result_tab = None
        st.rerun()
