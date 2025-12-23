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
st.set_page_config(page_title="Universal AI Studio (Final Stable)", page_icon="⚡", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: linear-gradient(to right, #c31432, #240b36); color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {font-size: 1.2rem !important; color: #333; border-bottom: 1px solid #eee; padding-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""

# --- HÀM HỖ TRỢ ---
def configure_genai(user_key=None):
    api_key = None
    if user_key:
        api_key = user_key
    else:
        try:
            if "SYSTEM_KEYS" in st.secrets:
                system_keys = st.secrets["SYSTEM_KEYS"]
                if isinstance(system_keys, str): 
                    clean_str = system_keys.replace('[','').replace(']','').replace('"','').replace("'",'')
                    system_keys = [k.strip() for k in clean_str.split(',') if k.strip()]
                if system_keys: api_key = random.choice(system_keys)
            elif "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]
        except: pass
    
    if not api_key: return False

    try:
        genai.configure(api_key=api_key)
        return True
    except: return False

def get_real_models():
    try:
        models = genai.list_models()
        valid_list = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                valid_list.append(m.name)
        valid_list.sort(reverse=True)
        
        priority_keywords = ["gemini-3.0-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash"]
        for keyword in priority_keywords:
            found = next((m for m in valid_list if keyword in m), None)
            if found:
                valid_list.insert(0, valid_list.pop(valid_list.index(found)))
                break
        return valid_list
    except:
        return ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

def get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type: return mime_type
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf': return 'application/pdf'
    if ext == '.txt': return 'text/plain'
    if ext == '.md': return 'text/md'
    if ext == '.csv': return 'text/csv'
    if ext in ['.mp3', '.wav', '.m4a']: return 'audio/mp3'
    return 'application/octet-stream'

def upload_to_gemini(path):
    mime = get_mime_type(path)
    file = genai.upload_file(path, mime_type=mime)
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def create_docx(content):
    doc = Document()
    doc.add_heading('BÁO CÁO PHÂN TÍCH AI', 0)
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = re.sub(r'\n\s*\n', '\n\n', clean_content)
    for line in clean_content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- MAIN APP ---
def main():
    st.title("🇻🇳 Universal AI Studio (Final Stable)")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🛠️ KHO VŨ KHÍ")
        
        # 1. CỐT LÕI
        st.markdown("### 1. Phân tích Cốt lõi")
        opt_transcript = st.checkbox("📝 Gỡ băng (Transcript)", False) 
        opt_summary = st.checkbox("📋 Tóm tắt nội dung", True)
        opt_action = st.checkbox("✅ Action Items", True)
        opt_process = st.checkbox("🔄 Trích xuất Quy trình", False)
        opt_prosody = st.checkbox("🎭 Phân tích Thái độ", False)
        opt_gossip = st.checkbox("☕ Chế độ Bà tám", False)

        # 2. SÁNG TẠO
        st.markdown("### 2. Sáng tạo Nghe/Nhìn")
        opt_podcast = st.checkbox("🎙️ Kịch bản Podcast", False)
        opt_video = st.checkbox("🎬 Kịch bản Video", False)
        opt_mindmap = st.checkbox("🧠 Sơ đồ tư duy", True)

        # 3. NGHIÊN CỨU
        st.markdown("### 3. Học tập & Nghiên cứu")
        opt_report = st.checkbox("📑 Báo cáo chuyên sâu", False)
        opt_briefing = st.checkbox("📄 Tài liệu tóm lược", False)
        opt_timeline = st.checkbox("⏳ Dòng thời gian", False)
        opt_quiz = st.checkbox("❓ Câu hỏi Trắc nghiệm", False)
        opt_flashcard = st.checkbox("🎴 Thẻ ghi nhớ", False)
        
        # 4. DỮ LIỆU
        st.markdown("### 4. Dữ liệu")
        opt_infographic = st.checkbox("📊 Dữ liệu Infographic", False)
        opt_slides = st.checkbox("🖥️ Dàn ý Slide", False)
        opt_table = st.checkbox("📉 Bảng số liệu", False)

        st.divider()
        
        # CẤU HÌNH ẨN
        with st.expander("⚙️ Cấu hình & API Key"):
            user_api_key = st.text_input("Nhập Key riêng:", type="password")
            is_connected = configure_genai(user_api_key)
            if is_connected:
                st.success("Đã kết nối!")
                real_models = get_real_models()
                model_version = st.selectbox("Model:", real_models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Chi tiết sâu"], value="Tiêu chuẩn")
            else:
                st.error("Chưa kết nối!")
                model_version = "models/gemini-1.5-flash"
                detail_level = "Tiêu chuẩn"

        if st.button("🗑️ Reset"):
            st.session_state.clear()
            st.rerun()

    # --- GIAO DIỆN TAB ---
    tab1, tab2 = st.tabs(["📂 Upload & Phân tích", "💬 Chat Tiếng Việt"])

    # === TAB 1 ===
    with tab1:
        col_up, col_rec = st.columns(2)
        with col_up:
            st.subheader("1. Upload File")
            uploaded_files = st.file_uploader("Chọn file (Audio, PDF, Text...)", type=['mp3', 'wav', 'm4a', 'pdf', 'txt', 'md', 'csv'], accept_multiple_files=True)
        with col_rec:
            st.subheader("2. Ghi âm")
            audio_bytes = audio_recorder()

        if st.button("🔥 BẮT ĐẦU PHÂN TÍCH", type="primary"):
            temp_paths = []
            if uploaded_files:
                for up_file in uploaded_files:
                    file_ext = os.path.splitext(up_file.name)[1]
                    if not file_ext: file_ext = ".txt"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
