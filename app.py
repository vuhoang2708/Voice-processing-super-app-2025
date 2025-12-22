import streamlit as st
import google.generativeai as genai
from docx import Document
from streamlit_mermaid import st_mermaid
from audio_recorder_streamlit import audio_recorder
import tempfile
import os
import time
import mimetypes

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio", page_icon="🌌", layout="wide")
st.markdown("""<style>.stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold;}</style>""", unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""

# --- HÀM HỖ TRỢ ---
def configure_genai():
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        return True
    except:
        st.error("🚨 Chưa nhập API Key trong Secrets!")
        return False

def get_real_models():
    try:
        models = genai.list_models()
        valid_list = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                valid_list.append(m.name)
        valid_list.sort(reverse=True) 
        return valid_list
    except:
        return ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

def get_mime_type(file_path):
    # Tự động xác định loại file để gửi cho Google
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type: return mime_type
    # Fallback thủ công nếu thư viện không nhận ra
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
    doc.add_heading('UNIVERSAL AI REPORT', 0)
    for line in content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- MAIN APP ---
def main():
    st.title("🌌 Universal AI Studio (Audio + PDF + Text)")
    if not configure_genai(): return

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🧠 Cấu hình AI")
        
        # 1. Chọn Model
        with st.spinner("Đang đồng bộ Model..."):
            real_models = get_real_models()
        if not real_models: st.error("Lỗi API Key"); return
        model_version = st.selectbox("Engine:", real_models)

        # 2. Chọn độ chi tiết (TÍNH NĂNG MỚI)
        detail_level = st.select_slider(
            "Độ chi tiết đầu ra:",
            options=["Ngắn gọn (Brief)", "Vừa phải (Standard)", "Chi tiết sâu (Deep Dive)"],
            value="Vừa phải (Standard)"
        )

        st.divider()
        st.header("🛠️ Bộ Công Cụ (Weapons)")
        
        st.markdown("**1. Phân tích cốt lõi**")
        opt_summary = st.checkbox("Tóm tắt & Action Items", True)
        opt_process = st.checkbox("Trích xuất Quy trình (Step-by-step)", False) # Hồi sinh
        opt_prosody = st.checkbox("Phân tích Cảm xúc/Thái độ", False) # Hồi sinh
        opt_gossip = st.checkbox("Chế độ 'Bà tám' (Gossip)", False) # Hồi sinh
        
        st.markdown("**2. Sáng tạo nội dung**")
        opt_audio_script = st.checkbox("Podcast Script", False)
        opt_video_script = st.checkbox("Video Script", False)
        opt_mindmap = st.checkbox("Mindmap (Sơ đồ tư duy)", True)
        
        st.markdown("**3. Học tập & Dữ liệu**")
        opt_report = st.checkbox("Báo cáo chuyên sâu (Formal)", False)
        opt_quiz = st.checkbox("Quiz / Flashcards", False)
        opt_data = st.checkbox("Bảng dữ liệu / Slide Outline", False)

        st.divider()
        if st.button("🗑️ Reset App"):
            st.session_state.clear()
            st.rerun()

    # --- GIAO DIỆN TAB ---
    tab1, tab2 = st.tabs(["📂 Upload & Phân tích", "💬 Chat Đa phương thức"])

    # === TAB 1 ===
    with tab1:
        col_up, col_rec = st.columns(2)
        files_to_process = []
        
        with col_up:
            st.subheader("1. Upload Đa năng")
            # Hỗ trợ thêm pdf, txt, md, csv
            uploaded_files = st.file_uploader(
                "Chọn file (Audio, PDF, Text...)", 
                type=['mp3', 'wav', 'm4a', 'pdf', 'txt', 'md', 'csv'], 
                accept_multiple_files=True
            )
        
        with col_rec:
            st.subheader("2. Ghi âm trực tiếp")
            audio_bytes = audio_recorder()

        if st.button("🔥 KÍCH HOẠT PHÂN TÍCH", type="primary"):
            # Gom file
            temp_paths = []
            if uploaded_files:
                for up_file in uploaded_files:
                    # Lấy đuôi file gốc để Gemini nhận diện đúng (quan trọng cho PDF)
                    file_ext = os.path.splitext(up_file.name)[1]
                    if not file_ext: file_ext = ".txt"
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                        tmp.write(up_file.getvalue())
                        temp_paths.append(tmp.name)
            
            if audio_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes)
                    temp_paths.append(tmp.name)
            
            if not temp_paths:
                st.warning("Chưa có dữ liệu đầu vào!")
            else:
                with st.spinner(f"Đang xử lý {len(temp_paths)} file với độ chi tiết: {detail_level}..."):
                    try:
                        gemini_files_objs = []
                        for path in temp_paths:
                            g_file = upload_to_gemini(path)
                            gemini_files_objs.append(g_file)
                            os.remove(path)
                        
                        st.session_state.gemini_files = gemini_files_objs
                        
                        # Prompt xây dựng theo yêu cầu
                        prompt = f"""
                        Bạn là trợ lý AI cao cấp. Hãy phân tích các tài liệu/file ghi âm được cung cấp.
                        
                        YÊU CẦU CHUNG:
                        - Độ chi tiết: {detail_level}.
                        - Ngôn ngữ: Tiếng Việt chuyên nghiệp (trừ khi yêu cầu khác).
                        
                        HÃY THỰC HIỆN CÁC NHIỆM VỤ SAU (Chỉ mục được chọn):
                        """
                        
                        if opt_summary: prompt += "\n- TÓM TẮT & ACTION ITEMS: Tóm tắt ý chính và liệt kê hành động cần làm (Ai, làm gì, deadline).\n"
                        if opt_process: prompt += "\n- QUY TRÌNH (PROCESS): Trích xuất các bước thực hiện dạng Step-by-step (Bước 1, Bước 2...).\n"
                        if opt_prosody: prompt += "\n- CẢM XÚC & THÁI ĐỘ: Phân tích ngữ điệu, sự do dự, căng thẳng hoặc đồng thuận của người nói (nếu là âm thanh).\n"
                        if opt_gossip: prompt += "\n- CHẾ ĐỘ BÀ TÁM: Kể lại nội dung theo phong cách hài hước, thân mật, dùng ngôn ngữ đời thường.\n"
                        
                        if opt_audio_script: prompt += "\n- PODCAST SCRIPT: Kịch bản đối thoại Host/Guest hấp dẫn.\n"
                        if opt_video_script: prompt += "\n- VIDEO SCRIPT: Kịch bản video 2 cột (Hình ảnh - Âm thanh).\n"
                        if opt_mindmap: prompt += "\n- MINDMAP: Mã code Mermaid.js (graph TD) trong block ```mermaid```.\n"
                        
                        if opt_report: prompt += "\n- BÁO CÁO CHUYÊN SÂU: Văn phong hành chính/học thuật, cấu trúc chặt chẽ.\n"
                        if opt_quiz: prompt += "\n- QUIZ & FLASHCARDS: Tạo câu hỏi trắc nghiệm và thẻ ghi nhớ.\n"
                        if opt_data: prompt += "\n- DỮ LIỆU: Trích xuất bảng biểu (Markdown Table) và dàn ý Slide.\n"

                        model = genai.GenerativeModel(model_version)
                        response = model.generate_content([prompt] + gemini_files_objs)
                        
                        st.session_state.analysis_result = response.text
                        st.success("✅ Xử lý xong!")
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
                st.download_button("📥 Tải báo cáo (.docx)", f, "Universal_Report.docx")
            os.remove(doc_io.name)

    # === TAB 2 ===
    with tab2:
        st.header("💬 Chat với Dữ liệu (Audio/PDF/Text)")
        if not st.session_state.gemini_files:
            st.info("👈 Vui lòng Upload file ở Tab 1 trước.")
        else:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
            if user_input := st.chat_input("Hỏi chi tiết về tài liệu/cuộc họp..."):
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"): st.markdown(user_input)
                with st.chat_message("assistant"):
                    with st.spinner("Đang suy nghĩ..."):
                        try:
                            # Chat dùng model đang chọn
                            chat_model = genai.GenerativeModel(model_version)
                            response = chat_model.generate_content(
                                st.session_state.gemini_files + 
                                [f"Yêu cầu: Trả lời câu hỏi dựa trên các file đã cung cấp. Độ chi tiết: {detail_level}. Câu hỏi: {user_input}"]
                            )
                            st.markdown(response.text)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e: st.error(f"Lỗi chat: {e}")

if __name__ == "__main__":
    main()
