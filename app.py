import streamlit as st
import google.generativeai as genai
from docx import Document
from streamlit_mermaid import st_mermaid
from audio_recorder_streamlit import audio_recorder
import tempfile
import os
import time
import mimetypes
import re
import random

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio Pro", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #c31432; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

# --- BIẾN TOÀN CỤC (CHỐNG LỖI SCOPE) ---
STRICT_RULES = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ. CẤM BỊA NỘI DUNG. TRÍCH DẪN GIỜ [mm:ss]."

# --- QUẢN LÝ SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""

# --- HÀM HỖ TRỢ ---
def configure_genai(user_key=None):
    api_key = user_key or st.secrets.get("GOOGLE_API_KEY") or (random.choice(st.secrets["SYSTEM_KEYS"]) if "SYSTEM_KEYS" in st.secrets else None)
    if not api_key: return False
    try:
        genai.configure(api_key=api_key)
        return True
    except: return False

def get_optimized_models():
    """LẤY DANH SÁCH THẬT VÀ ƯU TIÊN GEMINI-3-FLASH-PREVIEW"""
    try:
        models = genai.list_models()
        valid = [m.name for m in models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        
        # DANH SÁCH ƯU TIÊN (DÙNG ĐÚNG TÊN PREVIEW)
        priority = ["gemini-3-flash-preview", "gemini-2.0-flash-exp", "gemini-1.5-flash"]
        final_list = []
        
        for p in priority:
            found = [m for m in valid if p in m]
            for f in found:
                if f not in final_list: final_list.append(f)
        
        for v in valid:
            if v not in final_list: final_list.append(v)
            
        return final_list if final_list else ["models/gemini-1.5-flash"]
    except:
        return ["models/gemini-1.5-flash"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

# --- MAIN APP ---
def main():
    st.title("🛡️ Universal AI Studio (Fixed & Split)")
    
    with st.sidebar:
        st.header("🎯 CHẾ ĐỘ HOẠT ĐỘNG")
        main_mode = st.radio("Mục tiêu chính:", ("📝 Gỡ băng chi tiết", "📊 Phân tích chuyên sâu"))
        
        st.divider()
        
        if main_mode == "📊 Phân tích chuyên sâu":
            st.subheader("CHỌN VŨ KHÍ (TÁCH RIÊNG):")
            opt_summary = st.checkbox("📋 Tóm tắt nội dung", True)
            opt_action = st.checkbox("✅ Danh sách Hành động", True)
            opt_process = st.checkbox("🔄 Trích xuất Quy trình", False)
            opt_prosody = st.checkbox("🎭 Phân tích Cảm xúc", False)
            opt_mindmap = st.checkbox("🧠 Vẽ Sơ đồ tư duy", True)
            opt_quiz = st.checkbox("❓ Câu hỏi Trắc nghiệm", False)
            opt_flash = st.checkbox("🎴 Thẻ ghi nhớ", False)
            opt_slides = st.checkbox("🖥️ Dàn ý Slide", False)
        
        st.divider()
        with st.expander("⚙️ Cấu hình & Key"):
            user_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối!")
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", ["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")
            else: st.error("Chưa kết nối!")

        if st.button("🗑️ Reset App"): st.session_state.clear(); st.rerun()

    # --- TABS ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý Dữ liệu", "💬 Chat"])

    with tab_work:
        up_files = st.file_uploader("Upload file", accept_multiple_files=True)
        audio_bytes = audio_recorder()

        if st.button("🚀 BẮT ĐẦU THỰC THI", type="primary"):
            if not up_files and not audio_bytes:
                st.warning("Chưa có file!"); return

            temp_paths = []
            if up_files:
                for f in up_files:
                    ext = os.path.splitext(f.name)[1] or ".txt"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(f.getvalue()); temp_paths.append(tmp.name)
            if audio_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes); temp_paths.append(tmp.name)
            
            with st.spinner(f"Đang dùng {model_version} xử lý..."):
