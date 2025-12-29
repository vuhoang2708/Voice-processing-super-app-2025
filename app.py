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

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio (Time-Sync)", page_icon="⏱️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #1e3c72; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
    div[data-testid="stButton"] > button:contains("DỪNG") {background-color: #d32f2f !important;}
</style>
""", unsafe_allow_html=True)

# --- 2. BIẾN TOÀN CỤC ---
STRICT_RULES = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ. CẤM BỊA NỘI DUNG. BẮT BUỘC GHI MỐC THỜI GIAN [mm:ss] Ở ĐẦU MỖI ĐOẠN."

# --- 3. QUẢN LÝ SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""
if "is_auto_running" not in st.session_state: st.session_state.is_auto_running = False
if "loop_count" not in st.session_state: st.session_state.loop_count = 0

# --- 4. HÀM HỖ TRỢ ---
def configure_genai(user_key=None):
    api_key = user_key
    if not api_key:
        try:
            if "SYSTEM_KEYS" in st.secrets:
                keys = st.secrets["SYSTEM_KEYS"]
                if isinstance(keys, str): 
                    keys = [k.strip() for k in keys.replace('[','').replace(']','').replace('"','').replace("'",'').split(',')]
                if keys: api_key = random.choice(keys)
            elif "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]
        except: pass
    
    if not api_key: return False
    try:
        genai.configure(api_key=api_key)
        return True
    except: return False

def get_optimized_models():
    # Danh sách cứng để đảm bảo an toàn
    return ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-2.0-flash-exp"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def create_docx(content):
    doc = Document()
    doc.add_heading('BÁO CÁO', 0)
    clean_content = content.replace("```markdown", "").replace("```", "")
    for line in clean_content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

def get_safe_response(response):
    try:
        finish_reason = response.candidates[0].finish_reason
        if finish_reason in [1, 2]: return response.text
        elif finish_reason == 3: return "\n\n[CẢNH BÁO: Nội dung bị chặn do Safety.]"
        elif finish_reason == 4: return "\n\n[DỪNG: Phát hiện nội dung có bản quyền.]"
        else: return f"\n\n[Lỗi: Finish Reason {finish_reason}]"
    except: return response.text

def get_last_timestamp(text):
    """Tìm mốc thời gian cuối cùng trong văn bản dạng [mm:ss]"""
    matches = re.findall(r'\[(\d{1,2}:\d{2})\]', text)
    if matches:
        return matches[-1]
    return None

# --- 5. MAIN APP ---
def main():
    st.title("⏱️ Universal AI Studio (Time-Sync Fix)")
    
    with st.sidebar:
        st.header("🎯 CHẾ ĐỘ")
        main_mode = st.radio("Mục tiêu:", ("📝 Gỡ băng nguyên văn", "📊 Phân tích chuyên sâu"))
        
        if main_mode == "📊 Phân tích chuyên sâu":
            st.subheader("Vũ khí:")
            c1, c2 = st.columns(2)
            with c1:
                opt_summary = st.checkbox("📋 Tóm tắt", True)
                opt_action = st.checkbox("✅ Hành động", True)
                opt_process = st.checkbox("🔄 Quy trình", False)
            with c2:
                opt_prosody = st.checkbox("🎭 Cảm xúc", False)
                opt_mindmap = st.checkbox("🧠 Mindmap", True)
                opt_quiz = st.checkbox("❓ Quiz", False)
        else:
            st.info("Chế độ Gỡ băng sẽ chạy nối tiếp tự động.")
            auto_continue = st.checkbox("Tự động nối đoạn", value=True)
        
        st.divider()
        with st.expander("⚙️ Cấu hình & Key"):
            user_key = st.text_input("Key riêng:", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối!")
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
            else: st.error("Chưa kết nối!")

        if st.button("🗑️ Reset"):
            st.session_state.clear(); st.rerun()

    # --- TABS ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý", "💬 Chat"])

    with tab_work:
        if not st.session_state.is_auto_running:
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
                
                if not temp_paths:
                    st.warning("Chưa có file!")
                else:
                    with st.spinner(f"Đang xử lý với {model_version}..."):
                        try:
                            g_files = [upload_to_gemini(p) for p in temp_paths]
                            st.session_state.gemini_files = g_files
                            
                            # Tắt bộ lọc an toàn
                            safety_settings = [
                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                            ]
                            
                            gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2)

                            if main_mode.startswith("📝"):
                                prompt = f"""
                                {STRICT_RULES}
                                NHIỆM VỤ: Gỡ băng NGUYÊN VĂN 100%.
                                YÊU CẦU:
                                1. Bắt đầu mỗi câu bằng [Phút:Giây]. Ví dụ: [00:15] Xin chào...
                                2. Viết lại chính xác từng từ.
                                3. Định danh: 'Diễn giả'.
                                4. Ngôn ngữ: Tiếng Việt.
                                """
                                if auto_continue:
                                    st.session_state.is_auto_running = True
                                    st.session_state.loop_count = 1
                            else:
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Phân tích sâu:\n## TÓM TẮT\n## HÀNH ĐỘNG\n## QUY TRÌNH\n## CẢM XÚC\n## MÃ SƠ ĐỒ (Mermaid)\n## QUIZ"

                            model = genai.GenerativeModel(model_version)
                            response = model.generate_content(
                                [prompt] + g_files, 
                                generation_config=gen_config,
                                safety_settings=safety_settings
                            )
                            
                            safe_text = get_safe_response(response)
                            st.session_state.analysis_result = safe_text
                            st.rerun()
                        except Exception as e: st.error(f"Lỗi xử lý: {e}")

        # HIỂN THỊ KẾT QUẢ
        if st.session_state.analysis_result:
            if st.session_state.is_auto_running:
                st.warning(f"🔄 Đang tự động chạy tiếp (Vòng {st.session_state.loop_count})...")
                if st.button("🛑 DỪNG"):
                    st.session_state.is_auto_running = False
                    st.success("Đã dừng."); st.rerun()

            st.divider()
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

            doc = create_docx(res)
            doc_io = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(doc_io.name)
            with open(doc_io.name, "rb") as f:
                st.download_button("📥 Tải Báo Cáo", f, "Bao_Cao.docx", type="primary")
            os.remove(doc_io.name)

            # AUTO-CONTINUE
            if st.session_state.is_auto_running and main_mode.startswith("📝"):
                if "[DỪNG:" in res or "[CẢNH BÁO:" in res:
                    st.session_state.is_auto_running = False
                    st.error("⚠️ Dừng do bản quyền/an toàn.")
                else:
                    st.divider()
                    placeholder = st.empty()
                    for i in range(3, 0, -1):
                        placeholder.info(f"⏳ Chạy tiếp trong {i}s...")
                        time.sleep(1)
                    placeholder.empty()
                    
                    with st.spinner("Đang nghe tiếp..."):
                        try:
                            cont_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2)
                            model = genai.GenerativeModel(model_version)
                            
                            # --- LOGIC MỚI: TÌM MỐC THỜI GIAN CUỐI CÙNG ---
                            last_timestamp = get_last_timestamp(res)
                            last_part = res[-300:]
                            
                            if last_timestamp:
                                time_instruction = f"BẮT ĐẦU NGHE TỪ PHÚT {last_timestamp} TRỞ ĐI."
                            else:
                                time_instruction = "Tiếp tục ngay sau đoạn văn bản cuối cùng."

                            c_prompt = f"""
                            CONTEXT: Đang gỡ băng dở dang.
                            MỐC THỜI GIAN CUỐI CÙNG ĐÃ GHI: {last_timestamp}
                            ĐOẠN CUỐI VĂN BẢN: "...{last_part}"
                            
                            NHIỆM VỤ CẤP BÁCH:
                            1. {time_instruction}
                            2. Viết tiếp NGUYÊN VĂN đoạn sau.
                            3. TUYỆT ĐỐI KHÔNG quay lại từ đầu (00:00).
                            4. TUYỆT ĐỐI KHÔNG viết lại đoạn cũ.
                            5. Tiếp tục ghi mốc thời gian [mm:ss].
                            """
                            
                            safety_settings = [
                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                            ]

                            c_res = model.generate_content(
                                [c_prompt] + st.session_state.gemini_files, 
                                generation_config=cont_config,
                                safety_settings=safety_settings
                            )
                            
                            safe_c_text = get_safe_response(c_res)

                            if len(safe_c_text) < 50 or "kết thúc" in safe_c_text.lower() or "[DỪNG:" in safe_c_text:
                                st.session_state.is_auto_running = False
                                st.success("✅ Đã xong!")
                                if "[DỪNG:" in safe_c_text:
                                    st.session_state.analysis_result += "\n\n" + safe_c_text
                                    st.rerun()
                            else:
                                st.session_state.analysis_result += "\n\n" + safe_c_text
                                st.session_state.loop_count += 1
                                st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
                            st.session_state.is_auto_running = False

    with tab_chat:
        st.header("💬 Chat")
        if st.session_state.gemini_files:
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"]): st.markdown(m["content"])
            if inp := st.chat_input("Hỏi AI..."):
                st.session_state.chat_history.append({"role": "user", "content": inp})
                with st.chat_message("user"): st.markdown(inp)
                with st.chat_message("assistant"):
                    try:
                        m = genai.GenerativeModel(model_version)
                        r = m.generate_content(
                            st.session_state.gemini_files + [f"Trả lời: {inp}"],
                            safety_settings=SAFETY_SETTINGS
                        )
                        st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
                    except: st.error("Lỗi chat.")
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
