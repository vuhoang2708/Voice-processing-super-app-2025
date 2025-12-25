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
st.set_page_config(page_title="Universal AI Studio Pro", page_icon="🚀", layout="wide")

# --- 2. KHỞI TẠO SESSION STATE ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""
if "is_auto_running" not in st.session_state: st.session_state.is_auto_running = False
if "loop_count" not in st.session_state: st.session_state.loop_count = 0

# --- 3. TIÊU CHUẨN VẬN HÀNH (STRICT RULES) ---
STRICT_RULES = """
BẢN TIN CẬY TUYỆT ĐỐI (ANTI-HALLUCINATION):
1. CHỈ trích xuất thông tin có trong tệp nguồn. 
2. CẤM bịa đặt tên người, chức vụ hoặc mốc thời gian.
3. BẮT BUỘC trích dẫn mốc thời gian dạng [mm:ss] cho mỗi đoạn gỡ băng.
4. Nếu thông tin không rõ, ghi 'Dữ liệu nhiễu/Không xác định'.
5. Giữ nguyên các luồng ý kiến trái chiều (Debate), không tự ý hợp nhất.
"""

# --- 4. HÀM HỖ TRỢ & CƠ CHẾ RETRY ---
def configure_genai(user_key=None):
    api_key = user_key or ""
    if not api_key:
        try:
            if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
            elif "SYSTEM_KEYS" in st.secrets:
                keys = st.secrets["SYSTEM_KEYS"]
                api_key = random.choice(keys) if isinstance(keys, list) else keys
        except: pass
    
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

async def safe_generate_content(model, contents, config):
    """Triển khai Exponential Backoff (Thử lại 5 lần)"""
    for i in range(5):
        try:
            response = model.generate_content(contents, generation_config=config)
            return response
        except Exception as e:
            if i == 4: raise e
            wait_time = (2 ** i) + random.random()
            time.sleep(wait_time)
    return None

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def create_docx(content):
    doc = Document()
    doc.add_heading('BÁO CÁO PHÂN TÍCH CHUYÊN SÂU', 0)
    clean_content = content.replace("```markdown", "").replace("```", "")
    for line in clean_content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- 5. GIAO DIỆN CHÍNH ---
def main():
    try:
        st.markdown(f"""<h1 style='text-align: center; color: #2563eb;'>Universal AI Studio (Pro v3.0)</h1>""", unsafe_allow_html=True)
        
        with st.sidebar:
            st.header("🛠️ ĐIỀU KHIỂN")
            main_mode = st.radio("Chế độ:", ("📝 Gỡ băng (Transcript)", "📊 Phân tích (Analytics)"))
            
            st.divider()
            
            if main_mode.startswith("📊"):
                st.subheader("Báo cáo đầu ra:")
                opt_summary = st.checkbox("📋 Tóm tắt Dashboard", True)
                opt_action = st.checkbox("✅ Kế hoạch hành động", True)
                opt_mindmap = st.checkbox("🧠 Sơ đồ tư duy (Mindmap)", True)
                opt_debate = st.checkbox("⚖️ Luồng ý kiến trái chiều", True)
            else:
                auto_continue = st.checkbox("Tự động nối đoạn thông minh", value=True)
            
            st.divider()
            with st.expander("🔑 Cấu hình hệ thống"):
                user_key = st.text_input("API Key cá nhân:", type="password")
                if configure_genai(user_key):
                    st.success("Hệ thống: Sẵn sàng")
                    # Mặc định dùng engine 3.0 Flash (ID: gemini-2.5-flash-preview-09-2025)
                    model_version = "gemini-2.5-flash-preview-09-2025"
                else: st.error("Lỗi: Chưa có API Key")

            if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
                st.session_state.clear(); st.rerun()

        tab_work, tab_chat = st.tabs(["📂 Trung tâm Xử lý", "💬 Chat với Tài liệu"])

        with tab_work:
            if not st.session_state.is_auto_running:
                col_up, col_rec = st.columns(2)
                with col_up:
                    up_files = st.file_uploader("Kéo thả file (Audio/PDF/Docx)", accept_multiple_files=True)
                with col_rec:
                    st.write("Ghi âm trực tiếp:")
                    audio_bytes = audio_recorder(text="Bấm để ghi âm", pause_threshold=2.0)

                if st.button("🚀 KÍCH HOẠT XỬ LÝ", type="primary", use_container_width=True):
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
                        st.warning("Thông báo: Chưa có dữ liệu đầu vào.")
                    else:
                        with st.spinner("Đang tải dữ liệu lên Gemini Cloud..."):
                            try:
                                g_files = [upload_to_gemini(p) for p in temp_paths]
                                st.session_state.gemini_files = g_files
                                
                                gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.1)
                                model = genai.GenerativeModel(model_version)

                                if main_mode.startswith("📝"):
                                    prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Gỡ băng nguyên văn 100%. Định danh người nói là 'Diễn giả A', 'Diễn giả B'..."
                                    if auto_continue:
                                        st.session_state.is_auto_running = True
                                        st.session_state.loop_count = 1
                                else:
                                    prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Phân tích chuyên sâu dữ liệu.\n"
                                    if opt_summary: prompt += "## 📋 TÓM TẮT DASHBOARD (Dạng đối thoại)\n"
                                    if opt_action: prompt += "## ✅ KẾ HOẠCH HÀNH ĐỘNG (Ai - Làm gì - Deadline)\n"
                                    if opt_debate: prompt += "## ⚖️ PHÂN TÍCH TRANH LUẬN (Các ý kiến trái chiều)\n"
                                    if opt_mindmap: prompt += "## 🧠 MÃ SƠ ĐỒ (Mermaid code)\n"

                                response = model.generate_content([prompt] + g_files, generation_config=gen_config)
                                st.session_state.analysis_result = response.text
                                st.rerun()
                            except Exception as e: st.error(f"Lỗi API: {e}")

            # HIỂN THỊ KẾT QUẢ THEO STYLE COO
            if st.session_state.analysis_result:
                st.divider()
                res = st.session_state.analysis_result
                
                # Biểu đồ Mindmap
                if "```mermaid" in res:
                    with st.container():
                        st.subheader("🧠 Sơ đồ Tư duy Hệ thống")
                        try:
                            m_code = res.split("```mermaid")[1].split("```")[0]
                            st_mermaid(m_code, height=450)
                        except: st.info("Sơ đồ đang được xử lý...")

                # Nội dung chi tiết
                sections = res.split("## ")
                for s in sections:
                    if not s.strip(): continue
                    lines = s.split("\n")
                    header = lines[0].strip()
                    with st.expander(f"🔍 {header}", expanded=True):
                        st.markdown("\n".join(lines[1:]))

                # Xuất báo cáo
                doc = create_docx(res)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as doc_io:
                    doc.save(doc_io.name)
                    with open(doc_io.name, "rb") as f:
                        st.download_button("📥 TẢI BÁO CÁO (.DOCX)", f, "Bao_Cao_Universal_AI.docx", type="primary")
                
                # LOGIC TỰ ĐỘNG CHẠY TIẾP (LOOP)
                if st.session_state.is_auto_running and main_mode.startswith("📝"):
                    st.info(f"🔄 Đang nghe tiếp đoạn sau (Vòng {st.session_state.loop_count})...")
                    if st.button("🛑 DỪNG TỰ ĐỘNG"):
                        st.session_state.is_auto_running = False; st.rerun()
                    
                    time.sleep(2) # Chờ để user kịp nhìn
                    try:
                        last_anchor = res[-600:]
                        c_prompt = f"CONTEXT: Đã gỡ băng đến đoạn: '{last_anchor}'. NHIỆM VỤ: Viết tiếp nguyên văn phần còn lại từ file. KHÔNG lặp lại mỏ neo."
                        model = genai.GenerativeModel(model_version)
                        c_res = model.generate_content([c_prompt] + st.session_state.gemini_files)
                        
                        if len(c_res.text) < 30 or "kết thúc" in c_res.text.lower():
                            st.session_state.is_auto_running = False
                            st.success("Hệ thống: Đã hoàn tất gỡ băng toàn bộ file.")
                        else:
                            st.session_state.analysis_result += "\n\n" + c_res.text
                            st.session_state.loop_count += 1
                            st.rerun()
                    except: st.session_state.is_auto_running = False

        with tab_chat:
            st.header("💬 Trợ lý Tài liệu")
            if st.session_state.gemini_files:
                for m in st.session_state.chat_history:
                    with st.chat_message(m["role"]): st.markdown(m["content"])
                if inp := st.chat_input("Hỏi bất cứ điều gì về file đã upload..."):
                    st.session_state.chat_history.append({"role": "user", "content": inp})
                    with st.chat_message("user"): st.markdown(inp)
                    with st.chat_message("assistant"):
                        m = genai.GenerativeModel(model_version)
                        r = m.generate_content(st.session_state.gemini_files + [f"Dựa vào file, hãy trả lời: {inp}"])
                        st.markdown(r.text)
                        st.session_state.chat_history.append({"role": "assistant", "content": r.text})
            else: st.info("Vui lòng xử lý file ở tab 'Xử lý' trước khi chat.")

    except Exception as e:
        st.error(f"Hệ thống gặp sự cố: {e}")

if __name__ == "__main__":
    main()
