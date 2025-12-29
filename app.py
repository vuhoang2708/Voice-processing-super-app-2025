import streamlit as st
import google.generativeai as genai
from docx import Document
from streamlit_mermaid import st_mermaid
from audio_recorder_streamlit import audio_recorder
import tempfile
import os
import time
import mimetypes
import random

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio (Fixed)", page_icon="🛠️", layout="wide")

# --- 2. KHỞI TẠO SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""
if "is_auto_running" not in st.session_state: st.session_state.is_auto_running = False
if "loop_count" not in st.session_state: st.session_state.loop_count = 0

# --- 3. CẤU HÌNH AN TOÀN (QUAN TRỌNG ĐỂ FIX LỖI FINISH_REASON 2) ---
# Tắt toàn bộ bộ lọc để AI không chặn nội dung
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

STRICT_RULES = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ. CẤM BỊA NỘI DUNG. TRÍCH DẪN GIỜ [mm:ss]."

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

# --- 5. MAIN APP ---
def main():
    st.title("🛠️ Universal AI Studio (Safety Fix)")
    
    with st.sidebar:
        st.header("⚙️ CẤU HÌNH")
        
        # KHÔI PHỤC Ô CHỌN MODEL
        model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
        model_version = st.selectbox("Chọn Model:", model_options, index=0)
        
        st.divider()
        
        main_mode = st.radio("Chế độ:", ("📝 Gỡ băng (Transcript)", "📊 Phân tích (Analytics)"))
        
        if main_mode.startswith("📊"):
            st.subheader("Output:")
            opt_summary = st.checkbox("📋 Tóm tắt", True)
            opt_action = st.checkbox("✅ Hành động", True)
            opt_mindmap = st.checkbox("🧠 Mindmap", True)
        else:
            auto_continue = st.checkbox("Tự động nối đoạn", value=True)
        
        st.divider()
        with st.expander("🔑 API Key"):
            user_key = st.text_input("Key riêng:", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối!")
            else: st.error("Chưa kết nối!")

        if st.button("🗑️ Reset"):
            st.session_state.clear(); st.rerun()

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
                            
                            # Cấu hình Generation (Thêm safety_settings vào đây)
                            gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2)
                            model = genai.GenerativeModel(model_version)

                            if main_mode.startswith("📝"):
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Gỡ băng NGUYÊN VĂN 100%. Định danh: 'Diễn giả'. Viết Tiếng Việt."
                                if auto_continue:
                                    st.session_state.is_auto_running = True
                                    st.session_state.loop_count = 1
                            else:
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Phân tích sâu:\n"
                                if opt_summary: prompt += "## TÓM TẮT\n"
                                if opt_action: prompt += "## HÀNH ĐỘNG\n"
                                if opt_mindmap: prompt += "## MÃ SƠ ĐỒ (Mermaid)\n"

                            # GỌI API VỚI SAFETY SETTINGS
                            response = model.generate_content(
                                [prompt] + g_files, 
                                generation_config=gen_config,
                                safety_settings=SAFETY_SETTINGS # <--- FIX LỖI Ở ĐÂY
                            )
                            
                            st.session_state.analysis_result = response.text
                            st.rerun()
                        except Exception as e: st.error(f"Lỗi: {e}")

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
                        last_part = res[-500:]
                        c_prompt = f"""
                        CONTEXT: Đang gỡ băng dở dang.
                        MỎ NEO: "...{last_part}"
                        NHIỆM VỤ: Tìm mỏ neo, viết tiếp NGUYÊN VĂN đoạn sau. KHÔNG viết lại mỏ neo.
                        """
                        
                        c_res = model.generate_content(
                            [c_prompt] + st.session_state.gemini_files, 
                            generation_config=cont_config,
                            safety_settings=SAFETY_SETTINGS # <--- FIX LỖI Ở ĐÂY
                        )

                        if len(c_res.text) < 50 or "kết thúc" in c_res.text.lower():
                            st.session_state.is_auto_running = False
                            st.success("✅ Đã xong!")
                        else:
                            st.session_state.analysis_result += "\n\n" + c_res.text
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
                            safety_settings=SAFETY_SETTINGS # <--- FIX LỖI Ở ĐÂY
                        )
                        st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
                    except: st.error("Lỗi chat.")
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
