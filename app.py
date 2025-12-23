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
st.set_page_config(page_title="AI Meeting Assistant Pro", page_icon="🎙️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #c31432; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

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
    try:
        models = genai.list_models()
        valid = [m.name for m in models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        order = ["gemini-3.0-flash-preview", "gemini-1.5-flash", "gemini-1.5-pro"]
        final_list = []
        for target in order:
            for v in valid:
                if target in v and v not in final_list: final_list.append(v)
        return final_list if final_list else ["models/gemini-1.5-flash"]
    except: return ["models/gemini-1.5-flash"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

# --- MAIN APP ---
def main():
    st.title("🎙️ AI Meeting Assistant Pro")
    
    with st.sidebar:
        st.header("🛠️ KHO VŨ KHÍ")
        # Radio button để tách biệt nhiệm vụ như bác yêu cầu
        main_mode = st.radio("Mục tiêu chính:", ("📝 Gỡ băng chi tiết", "📊 Phân tích chuyên sâu"))
        
        if main_mode == "📊 Phân tích chuyên sâu":
            st.subheader("Tính năng:")
            c1, c2 = st.columns(2)
            with c1:
                opt_summary = st.checkbox("📋 Tóm tắt", True)
                opt_action = st.checkbox("✅ Hành động", True)
            with c2:
                opt_mindmap = st.checkbox("🧠 Mindmap", True)
                opt_prosody = st.checkbox("🎭 Cảm xúc", False)
        
        st.divider()
        with st.expander("⚙️ Cấu hình & Key", expanded=False):
            user_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_key):
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", ["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")

        if st.button("🗑️ Reset App"):
            st.session_state.clear(); st.rerun()

    # --- TABS ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý Dữ liệu", "💬 Chat"])

    with tab_work:
        up_files = st.file_uploader("Upload file", accept_multiple_files=True)
        audio_bytes = audio_recorder()

        if st.button("🚀 BẮT ĐẦU", type="primary"):
            temp_paths = []
            if up_files:
                for f in up_files:
                    ext = os.path.splitext(f.name)[1] or ".txt"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(f.getvalue()); temp_paths.append(tmp.name)
            if audio_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes); temp_paths.append(tmp.name)
            
            if temp_paths:
                with st.spinner("AI đang xử lý..."):
                    try:
                        g_files = [upload_to_gemini(p) for p in temp_paths]
                        st.session_state.gemini_files = g_files
                        
                        # Dùng cấu hình ổn định nhất của AI Studio
                        gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2)
                        model = genai.GenerativeModel(model_version)

                        if main_mode.startswith("📝"):
                            prompt = "Hãy gỡ băng NGUYÊN VĂN 100% nội dung file này. Ghi rõ mốc thời gian [mm:ss] và định danh người nói là 'Diễn giả'. Viết Tiếng Việt."
                        else:
                            prompt = f"Phân tích chuyên sâu (Độ chi tiết: {detail_level}) các mục: Tóm tắt, Hành động, Mindmap, Cảm xúc. Trả lời Tiếng Việt."

                        response = model.generate_content([prompt] + g_files, generation_config=gen_config)
                        st.session_state.analysis_result = response.text
                        st.success("✅ Đã hoàn thành.")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
            else: st.warning("Chưa có file!")

        if st.session_state.analysis_result:
            res = st.session_state.analysis_result
            sections = res.split("## ")
            for s in sections:
                if not s.strip(): continue
                lines = s.split("\n")
                with st.expander(f"📌 {lines[0].strip()}", expanded=True):
                    st.markdown("\n".join(lines[1:]))

            if main_mode.startswith("📝") and st.button("⏭️ Viết tiếp đoạn sau"):
                with st.spinner("Đang nghe tiếp..."):
                    try:
                        # Khai báo trực tiếp để tránh lỗi UnboundLocalError
                        model_cont = genai.GenerativeModel(model_version)
                        c_prompt = f"Tiếp tục gỡ băng NGUYÊN VĂN đoạn sau của file này. Đoạn trước đã kết thúc ở: '{res[-200:]}'"
                        c_res = model_cont.generate_content([c_prompt] + st.session_state.gemini_files, generation_config=genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2))
                        st.session_state.analysis_result += "\n\n(PHẦN TIẾP)\n\n" + c_res.text
                        st.rerun()
                    except Exception as e: st.error(f"Lỗi: {e}")

    with tab_chat:
        st.header("💬 Chat với file")
        if st.session_state.gemini_files:
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"]): st.markdown(m["content"])
            if inp := st.chat_input("Hỏi AI..."):
                st.session_state.chat_history.append({"role": "user", "content": inp})
                with st.chat_message("user"): st.markdown(inp)
                with st.chat_message("assistant"):
                    m_chat = genai.GenerativeModel(model_version)
                    r = m_chat.generate_content(st.session_state.gemini_files + [f"Dựa trên file, trả lời Tiếng Việt: {inp}"])
                    st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
