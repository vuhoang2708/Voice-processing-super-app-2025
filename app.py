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
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: linear-gradient(to right, #2c3e50, #000000); color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

# --- QUẢN LÝ SESSION STATE ---
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

def get_real_models():
    try:
        models = genai.list_models()
        valid_list = [m.name for m in models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        valid_list.sort(reverse=True)
        # Ưu tiên 3.0 Flash lên đầu
        for kw in ["gemini-3.0-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            found = [m for m in valid_list if kw in m]
            if found:
                valid_list.insert(0, valid_list.pop(valid_list.index(found[0])))
                break
        return valid_list
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
    st.title("🛡️ AI Studio Pro (Hallucination-Free Edition)")
    
    # --- SIDEBAR: KHO VŨ KHÍ ---
    with st.sidebar:
        st.header("🛠️ KHO VŨ KHÍ")
        main_mode = st.radio("Mục tiêu chính:", ("📝 Gỡ băng nguyên văn (Transcript)", "📊 Phân tích chuyên sâu (Analysis)"))
        
        if main_mode == "📊 Phân tích chuyên sâu (Analysis)":
            st.subheader("Tính năng:")
            c1, c2 = st.columns(2)
            with c1:
                opt_summary = st.checkbox("📋 Tóm tắt", True)
                opt_action = st.checkbox("✅ Hành động", True)
                opt_process = st.checkbox("🔄 Quy trình", False)
            with c2:
                opt_prosody = st.checkbox("🎭 Cảm xúc", False)
                opt_mindmap = st.checkbox("🧠 Mindmap", True)
                opt_quiz = st.checkbox("❓ Quiz/Slide", False)
        
        st.divider()
        with st.expander("⚙️ Cấu hình & Key"):
            user_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối!")
                models = get_real_models()
                model_version = st.selectbox("Engine:", models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")
            else: st.error("Chưa kết nối API!")

        if st.button("🗑️ Reset"):
            st.session_state.clear(); st.rerun()

    tab_work, tab_chat = st.tabs(["📂 Xử lý", "💬 Chat"])

    with tab_work:
        up_files = st.file_uploader("Upload Audio/PDF/Text", accept_multiple_files=True)
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
                with st.spinner("AI đang đối chiếu dữ liệu gốc..."):
                    try:
                        g_files = [upload_to_gemini(p) for p in temp_paths]
                        st.session_state.gemini_files = g_files
                        
                        # CẤU HÌNH CHỐNG BỊA CHUYỆN TUYỆT ĐỐI
                        gen_config = genai.types.GenerationConfig(
                            max_output_tokens=8192,
                            temperature=0.0, # KHÔNG SÁNG TẠO
                            top_p=0.1,       # CHỈ CHỌN ĐÁP ÁN CHẮC CHẮN NHẤT
                        )
                        
                        common_rules = """
                        NGUYÊN TẮC 'GROUNDING' BẮT BUỘC:
                        1. CHỈ SỬ DỤNG thông tin có trong các file được cung cấp.
                        2. TUYỆT ĐỐI KHÔNG sử dụng kiến thức bên ngoài hoặc dự đoán thông tin thiếu.
                        3. Nếu thông tin không có trong file, phải trả lời là 'Nội dung này không có trong dữ liệu gốc'.
                        4. TUYỆT ĐỐI KHÔNG đoán tên người, tên công ty hay địa danh nếu không được xưng danh rõ ràng trong file.
                        5. Cung cấp mốc thời gian [phút:giây] cho mọi luận điểm quan trọng.
                        """

                        if main_mode.startswith("📝"):
                            prompt = f"{common_rules}\nNHIỆM VỤ: Gỡ băng nguyên văn (Verbatim) từng lời nói. Không tóm tắt. Viết Tiếng Việt."
                        else:
                            prompt = f"{common_rules}\nNHIỆM VỤ: Phân tích chuyên sâu (Độ chi tiết: {detail_level}).\n"
                            if opt_summary: prompt += "## TÓM TẮT NỘI DUNG\n"
                            if opt_action: prompt += "## HÀNH ĐỘNG CẦN LÀM\n"
                            if opt_process: prompt += "## QUY TRÌNH\n"
                            if opt_prosody: prompt += "## THÁI ĐỘ NGỮ ĐIỆU\n"
                            if opt_mindmap: prompt += "## MÃ SƠ ĐỒ (Mermaid block)\n"
                            if opt_quiz: prompt += "## QUIZ & SLIDE OUTLINE\n"

                        model = genai.GenerativeModel(model_version)
                        response = model.generate_content([prompt] + g_files, generation_config=gen_config)
                        st.session_state.analysis_result = response.text
                        st.success("✅ Đã hoàn thành xử lý an toàn.")
                    except Exception as e: st.error(f"Lỗi: {e}")
            else: st.warning("Chưa có file!")

        if st.session_state.analysis_result:
            res = st.session_state.analysis_result
            if "```mermaid" in res:
                try:
                    m_code = res.split("```mermaid")[1].split("```")[0]
                    st_mermaid(m_code, height=500)
                except: pass
            
            sections = res.split("## ")
            for s in sections:
                if not s.strip(): continue
                lines = s.split("\n")
                with st.expander(f"📌 {lines[0].strip()}", expanded=True):
                    st.markdown("\n".join(lines[1:]))

            if main_mode.startswith("📝") and st.button("⏭️ Tiếp tục đoạn sau (Nếu bị ngắt)"):
                with st.spinner("Đang nghe tiếp..."):
                    model = genai.GenerativeModel(model_version)
                    c_prompt = f"Tiếp tục gỡ băng NGUYÊN VĂN đoạn tiếp theo của file. Bắt đầu ngay sau đoạn: '{res[-200:]}'"
                    c_res = model.generate_content([c_prompt] + st.session_state.gemini_files, generation_config=gen_config)
                    st.session_state.analysis_result += "\n\n--- PHẦN TIẾP THEO ---\n\n" + c_res.text
                    st.rerun()

    with tab_chat:
        st.header("💬 Chat bảo mật")
        if st.session_state.gemini_files:
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"]): st.markdown(m["content"])
            if inp := st.chat_input("Hỏi AI..."):
                st.session_state.chat_history.append({"role": "user", "content": inp})
                with st.chat_message("user"): st.markdown(inp)
                with st.chat_message("assistant"):
                    m = genai.GenerativeModel(model_version)
                    r = m.generate_content(st.session_state.gemini_files + [f"TRẢ LỜI DUY NHẤT TỪ FILE, TEMPERATURE 0: {inp}"])
                    st.markdown(r.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": r.text})
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
