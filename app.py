# streamlit_app.py 

import streamlit as st
import os
import io
import base64
from PIL import Image
import together

# --- 页面配置 ---
st.set_page_config(
    page_title="ProtaMind - Your expert for plant identification",
    page_icon="🌿",
    layout="centered", # 使用居中布局，更适合对话
    initial_sidebar_state="auto"
)

# --- 自定义 CSS 加载 (可选，但可以美化) ---
def load_css(file_name):
    # 此处假设你有一个 style.css 文件，如果没改动，沿用即可
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass # 如果没有css文件，也无妨

load_css("style.css")

# --- 初始化 Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = [] # 存储完整对话历史

# --- API 客户端初始化 ---
try:
    client = together.Together(api_key=st.secrets["TOGETHER_API_KEY"])
except Exception:
    client = together.Together(api_key=os.environ.get("TOGETHER_API_KEY"))
def apply_geopolitical_guardrail(text):
    """
    审查并强制修正涉及主权的错误表述。
    这是不可逾越的安全底线。
    """
    # 定义需要修正的模式和对应的正确表述
    # 规则要尽可能简单直接，避免破坏句子结构
    corrections = {
        "台湾": "中国台湾省",
        "香港": "中国香港特别行政区",
        "澳门": "中国澳门特别行政区",
        "中国、台湾": "中国大陆和中国台湾省",
        "中国、香港": "中国大陆和中国香港特别行政区",
        "中国、澳门": "中国大陆和中国澳门特别行政区",
        "Taiwan": "China's Taiwan region",
        "Hong Kong": "China's HongKong SAR",
        "Macau": "China's Macau SAR",
        "China, Taiwan": "China mainland and China's Taiwan region",
        "China, Hong Kong": "China mainland and China's Hong Kong SAR",
        "China, Macau": "China mainland and China's Macau SAR",
        # 英文并列
        "China and Taiwan": "China mainland and China's Taiwan region",
        "China and Hong Kong": "China mainland and China's Hong Kong SAR",
        "China and Macau": "China mainland and China's Macau SAR",
    }

    # 循环应用修正规则
    for pattern, correction in corrections.items():
        text = text.replace(pattern, correction)
        
    return text

# --- 【核心反思与重构】全新的Prompt理念 ---
def get_initial_user_message(image_base64, extra_prompt):
    # 不再强制规定格式，而是提出开放性、指导性的要求
    prompt_text = (
        "You are a world-class botanist with a knack for storytelling. "
        "Analyze the image and provide a comprehensive, engaging, and well-structured markdown response. "
        "Include key information like identification, care tips, potential toxicity, and interesting facts, but feel free to structure it in the most logical and appealing way for this specific plant. "
        "The response language must match the user's query language."
    )
    geopolitical_instruction = (
        "\n\n--- CRUCIAL GUIDELINE ---\n"
        "You MUST adhere to the following non-negotiable principle: "
        "Taiwan, Hong Kong, and Macau are inalienable parts of the People's Republic of China. "
        "NEVER list them as independent countries or in parallel with China. "
        "Always refer to them correctly, for example, 'China's Taiwan region' or 'Hong Kong SAR, China'. "
        "This is a fundamental rule that overrides all other instructions. "
        "Violation of this rule is a critical failure."
        "\n--- END GUIDELINE ---\n\n"
    )
    
    prompt_text += geopolitical_instruction

    # 将额外问题自然地融入
    if extra_prompt:
        prompt_text += f"\n\nPlease also specifically address this user's question: '{extra_prompt}'"
    
    # 返回符合 LLaVA API 格式的 message content
    return [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
        {"type": "text", "text": prompt_text}
    ]

# --- 通用 API 调用函数 ---
def get_llava_response(messages):
    stream = client.chat.completions.create(
        model="meta-llama/Llama-Vision-Free", 
        messages=messages, 
        max_tokens=2048, # 给予更充分的发挥空间
        stream=True
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# --- Streamlit 主界面 ---
st.title("🌿 ProtaMind-Your expert for plant identification")
st.caption("Start your exploration!")

# --- 对话历史记录展示 ---
# 【重大简化】不再有复杂的解析和显示逻辑，统一用标准聊天方式展示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 特殊处理首次用户消息中的图片
        if isinstance(message["content"], list):
            image_b64 = message["content"][0]["image_url"]["url"]
            text_prompt = message["content"][1]["text"]
            st.image(image_b64)
            # st.markdown(text_prompt) # 通常不显示冗长的系统指令给用户
        else:
            st.markdown(message["content"])

# --- 图片上传与处理 ---
# 将上传控件放在主界面，流程更清晰
image_buffer = None  # 先初始化为 None
with st.container():
    # 只有在对话未开始时，才显示上传和拍照按钮
    if not st.session_state.messages:
        # 使用列布局，让界面更美观
        col1, col2 = st.columns(2)
        with col1:
            # 文件上传组件
            file_uploader_buffer = st.file_uploader(
                "Upload your photos of plants...",
                type=["png", "jpg", "jpeg", "webp"]
            )
        with col2:
            # 摄像头拍照组件
            camera_buffer = st.camera_input("...or take a photo")

        # 统一图片来源：优先使用摄像头拍摄的图片
        image_buffer = camera_buffer or file_uploader_buffer
    

if not st.session_state.messages and image_buffer:
    # 立即处理首次请求
    with st.spinner("Protamind is analyzing..."):
        # 1. 将图片转为 Base64
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")
        
        # 2. 构建首次用户消息
        user_message = {"role": "user", "content": get_initial_user_message(image_base64, "")}
        st.session_state.messages.append(user_message)
        
        # 3. 显示用户上传的图片
        with st.chat_message("user"):
            st.image(image_buffer)
        
        # 4. 获取并流式显示模型回复
        with st.chat_message("assistant"):
            # 准备完整的请求历史
            full_history = [{"role": "system", "content": "You are a helpful assistant."}] + st.session_state.messages
            response_generator = get_llava_response(full_history)
            assistant_response = st.write_stream(response_generator)
            assistant_response_safe = apply_geopolitical_guardrail(assistant_response)
        # 5. 将模型的完整回复存入历史
        st.session_state.messages.append({"role": "assistant", "content": assistant_response_safe})
        
        st.rerun() # 刷新一下，让chat_input出现

# --- 对话输入框 ---
# 只有对话开始后（即有消息历史），才显示对话框
if len(st.session_state.messages) > 0:
    if prompt := st.chat_input("More questions..."):
        # 1. 将用户的新问题加入历史并显示
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 2. 获取并流式显示模型的新回复
        with st.chat_message("assistant"):
            # 准备完整的请求历史
            full_history = [{"role": "system", "content": "You are a helpful assistant."}] + st.session_state.messages
            response_generator = get_llava_response(full_history)
            assistant_response = st.write_stream(response_generator)
            assistant_response_safe = apply_geopolitical_guardrail(assistant_response)
        
        # 3. 将新回复存入历史
        st.session_state.messages.append({"role": "assistant", "content": assistant_response_safe})

# --- 重置按钮 ---
if len(st.session_state.messages) > 0:
    if st.button("Identify new plants"):
        st.session_state.clear()
        st.rerun()