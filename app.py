import streamlit as st
import google.generativeai as genai
from docx import Document
from streamlit_mermaid import st_mermaid
from streamlit_audio_recorder import st_audio_recorder
import tempfile
import os
import time

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="NotebookLM Ultimate", page_icon="💎", layout="wide")
st.markdown("""<style>.stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold;}</style>""", unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "gemini_files" not in st.session_state:
    st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""

# --- HÀM HỖ TRỢ ---
def configure_genai():
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        return True
    except:
        st.error("🚨 Chưa nhập API Key trong Secrets!")
        return False

def upload_to_gemini(path, mime_type="audio/mp3"):
    file = genai.upload_file(path, mime_type=mime_type)
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def create_docx(content):
    doc = Document()
    doc.add_heading('NOTEBOOKLM ULTIMATE REPORT', 0)
    for line in content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- MAIN APP ---
def main():
    st.title("💎 NotebookLM Ultimate (9 Weapons + Chat + Live)")
    
    if not configure_genai(): return

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🧠 Model Engine")
        model_version = st.selectbox(
            "Chọn Model:",
            ("gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro")
        )
        
        st.divider()
        st.header("🛠️ 9 VŨ KHÍ (Cho Tab Phân tích)")
        
        st.caption("1. Nghe & Nhìn")
        opt_audio_script = st.checkbox("Podcast Script", True)
        opt_video_script = st.checkbox("Video Script", False)
        
        st.caption("2. Hệ thống hóa")
        opt_mindmap = st.checkbox("Mindmap (Sơ đồ tư duy)", True)
        opt_report = st.checkbox("Deep Report", False)
        
        st.caption("3. Học tập")
        opt_flashcard = st.checkbox("Flashcards", False)
        opt_quiz = st.checkbox("Quiz (Trắc nghiệm)", False)
        
        st.caption("4. Dữ liệu")
        opt_infographic = st.checkbox("Infographic Data", False)
        opt_slides = st.checkbox("Slide Outline", False)
        opt_table = st.checkbox("Data Table", False)
        
        st.divider()
        if st.button("🗑️ Xóa dữ liệu & Làm mới"):
            st.session_state.chat_history = []
            st.session_state.gemini_files = []
            st.session_state.analysis_result = ""
            st.rerun()

    # --- GIAO DIỆN TAB ---
    tab1, tab2 = st.tabs(["📂 Upload & 9 Vũ Khí", "💬 Chat Chi Tiết"])

    # ================= TAB 1: UPLOAD & PHÂN TÍCH =================
    with tab1:
        col_up, col_rec = st.columns(2)
        files_to_process = []
        
        with col_up:
            st.subheader("1. Upload File (Nhiều file)")
            uploaded_files = st.file_uploader("Chọn file (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a'], accept_multiple_files=True)
        
        with col_rec:
            st.subheader("2. Ghi âm trực tiếp")
            audio_bytes = st_audio_recorder()

        if st.button("🔥 KÍCH HOẠT PHÂN TÍCH (9 VŨ KHÍ)", type="primary"):
            # Gom file
            temp_paths = []
            if uploaded_files:
                for up_file in uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        tmp.write(up_file.getvalue())
                        temp_paths.append(tmp.name)
            if audio_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes)
                    temp_paths.append(tmp.name)
            
            if not temp_paths:
                st.warning("Chưa có file nào để xử lý!")
            else:
                with st.spinner(f"Đang upload {len(temp_paths)} file lên Google & Xử lý..."):
                    try:
                        gemini_files_objs = []
                        for path in temp_paths:
                            g_file = upload_to_gemini(path)
                            gemini_files_objs.append(g_file)
                            os.remove(path)
                        
                        st.session_state.gemini_files = gemini_files_objs
                        
                        prompt = "Bạn là chuyên gia NotebookLM. Phân tích các file âm thanh và tạo nội dung sau (chỉ mục được chọn):\n"
                        if opt_audio_script: prompt += "- PODCAST SCRIPT: Kịch bản đối thoại Host/Guest.\n"
                        if opt_video_script: prompt += "- VIDEO SCRIPT: Kịch bản video 2 cột.\n"
                        if opt_mindmap: prompt += "- MINDMAP: Mã code Mermaid.js (graph TD) trong block ```mermaid```.\n"
                        if opt_report: prompt += "- DEEP REPORT: Báo cáo chuyên sâu.\n"
                        if opt_flashcard: prompt += "- FLASHCARDS: 5-10 thẻ ghi nhớ.\n"
                        if opt_quiz: prompt += "- QUIZ: 5 câu trắc nghiệm có giải thích.\n"
                        if opt_infographic: prompt += "- INFOGRAPHIC DATA: Số liệu/Điểm nhấn.\n"
                        if opt_slides: prompt += "- SLIDE OUTLINE: Dàn ý thuyết trình.\n"
                        if opt_table: prompt += "- DATA TABLE: Bảng dữ liệu Markdown.\n"

                        model = genai.GenerativeModel(model_version)
                        response = model.generate_content([prompt] + gemini_files_objs)
                        
                        st.session_state.analysis_result = response.text
                        st.success("✅ Xử lý xong! Chuyển sang Tab Chat để hỏi thêm nếu cần.")

                    except Exception as e:
                        st.error(f"Lỗi: {e}")

        if st.session_state.analysis_result:
            st.divider()
            content = st.session_state.analysis_result
            
            if "```mermaid" in content:
                st.subheader("🧠 Bản đồ tư duy")
                try:
                    mermaid_code = content.split("```mermaid")[1].split("```")[0]
                    st_mermaid(mermaid_code, height=500)
                except: pass
            
            st.markdown(content)
            
            doc = create_docx(content)
            doc_io = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(doc_io.name)
            with open(doc_io.name, "rb") as f:
                st.download_button("📥 Tải báo cáo (.docx)", f, "NotebookLM_Ultimate.docx")
            os.remove(doc_io.name)

    # ================= TAB 2: CHAT VỚI DỮ LIỆU =================
    with tab2:
        st.header("💬 Chat với nội dung ghi âm")
        if not st.session_state.gemini_files:
            st.info("👈 Vui lòng Upload và bấm 'Kích hoạt phân tích' ở Tab 1 trước.")
        else:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            if user_input := st.chat_input("Hỏi chi tiết về cuộc họp..."):
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.markdown(user_input)
                
                with st.chat_message("assistant"):
                    with st.spinner("Đang nghe lại băng ghi âm..."):
                        try:
                            chat_model = genai.GenerativeModel("gemini-1.5-flash")
                            response = chat_model.generate_content(
                                st.session_state.gemini_files + 
                                [f"Context: Đây là nội dung các file ghi âm. Hãy trả lời câu hỏi: {user_input}"]
                            )
                            st.markdown(response.text)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e:
                            st.error(f"Lỗi chat: {e}")

if __name__ == "__main__":
    main()
