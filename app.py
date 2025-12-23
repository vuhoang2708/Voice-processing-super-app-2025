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
st.set_page_config(page_title="AI Studio Pro Max", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #c31432; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
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

def get_real_models():
    """Hàm lấy danh sách model và cưỡng ép đưa 3.0 Flash Preview lên đầu"""
    try:
        models = genai.list_models()
        valid_list = [m.name for m in models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        
        # CƯỠNG ÉP DANH SÁCH ƯU TIÊN
        preferred = ["models/gemini-3.0-flash-preview", "models/gemini-3.0-flash", "models/gemini-2.0-flash-exp", "models/gemini-1.5-flash"]
        
        final_list = []
        # Nạp các con ưu tiên trước
        for p in preferred:
            if p in valid_list: final_list.append(p)
        
        # Nếu không quét thấy 3.0 nhưng bác muốn dùng, tôi nạp cứng luôn (để lỡ thư viện cũ nó không thấy)
        if "models/gemini-3.0-flash-preview" not in final_list:
            final_list.insert(0, "models/gemini-3.0-flash-preview")

        # Nạp nốt số còn lại
        for v in valid_list:
            if v not in final_list: final_list.append(v)
            
        return final_list
    except:
        return ["models/gemini-3.0-flash-preview", "models/gemini-1.5-flash"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

# --- MAIN APP ---
def main():
    st.title("🛡️ Universal AI Studio (Vibe Coding Dec 2025)")
    
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
        # CẤU HÌNH XUỐNG ĐÁY
        with st.expander("⚙️ Cấu hình & API Key", expanded=False):
            user_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối!")
                models = get_real_models()
                model_version = st.selectbox("Chọn Engine:", models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")
            else: st.error("Chưa kết nối API!")

        if st.button("🗑️ Reset"): st.session_state.clear(); st.rerun()

    tab_work, tab_chat = st.tabs(["📂 Xử lý Dữ liệu", "💬 Chat Chuyên sâu"])

    with tab_work:
        up_files = st.file_uploader("Upload Audio/PDF/Text", accept_multiple_files=True)
        audio_bytes = audio_recorder()

        if st.button("🚀 BẮT ĐẦU THỰC THI", type="primary"):
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
                with st.spinner("AI đang làm việc..."):
                    try:
                        g_files = [upload_to_gemini(p) for p in temp_paths]
                        st.session_state.gemini_files = g_files
                        
                        gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.1, top_p=0.1)
                        
                        # ANTI-HALLUCINATION RULES
                        rules = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ (gọi là Người nói 1). CẤM BỊA NỘI DUNG. TRÍCH DẪN MỐC GIỜ [mm:ss]."
                        
                        if main_mode.startswith("📝"):
                            prompt = f"{rules}\nNHIỆM VỤ: Gỡ băng nguyên văn 100%. Viết Tiếng Việt."
                        else:
                            prompt = f"{rules}\nNHIỆM VỤ: Phân tích sâu {detail_level} cho các mục: Tóm tắt, Hành động, Quy trình, Cảm xúc, Mindmap, Quiz."

                        # SILENT FALLBACK SYSTEM
                        retry_list = [model_version, "models/gemini-1.5-flash", "models/gemini-1.5-pro"]
                        retry_list = list(dict.fromkeys(retry_list))
                        
                        final_response = None
                        current_used_model = ""
                        
                        for m_name in retry_list:
                            try:
                                model = genai.GenerativeModel(m_name)
                                final_response = model.generate_content([prompt] + g_files, generation_config=gen_config)
                                current_used_model = m_name
                                break
                            except Exception as e:
                                if "429" in str(e) or "Quota" in str(e): continue
                                else: st.error(f"Lỗi: {e}"); break
                        
                        if final_response:
                            st.session_state.analysis_result = final_response.text
                            st.success(f"✅ Xử lý thành công bằng {current_used_model}")
                        else:
                            st.error("❌ Tất cả các model đều hết Quota. Vui lòng thử lại sau.")

                    except Exception as e: st.error(f"Lỗi: {e}")
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
                        cont_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.1)
                        model = genai.GenerativeModel(model_version)
                        last_text = res[-300:]
                        c_prompt = f"{rules}\nBạn đang gỡ băng đến đoạn: '{last_text}'. Hãy viết tiếp NGUYÊN VĂN đoạn sau."
                        c_res = model.generate_content([c_prompt] + st.session_state.gemini_files, generation_config=cont_config)
                        st.session_state.analysis_result += "\n\n(PHẦN TIẾP)\n\n" + c_res.text
                        st.rerun()
                    except Exception as e: st.error(f"Lỗi: {e}")

    with tab_chat:
        st.header("💬 Chat")
        if st.session_state.gemini_files:
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"]): st.markdown(m["content"])
            if inp := st.chat_input("Hỏi AI..."):
                st.session_state.chat_history.append({"role": "user", "content": inp})
                with st.chat_message("user"): st.markdown(inp)
                with st.chat_message("assistant"):
                    m = genai.GenerativeModel(model_version)
                    r = m.generate_content(st.session_state.gemini_files + [f"TRẢ LỜI TỪ FILE: {inp}"])
                    st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
