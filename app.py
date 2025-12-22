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

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio Pro", page_icon="🌌", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: linear-gradient(to right, #4b6cb7, #182848); color: white;}
    .stExpander {border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

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
        # Đưa Pro lên đầu để khuyến khích dùng cho Deep Dive
        if "models/gemini-1.5-pro" in valid_list:
            valid_list.insert(0, valid_list.pop(valid_list.index("models/gemini-1.5-pro")))
        return valid_list
    except:
        return ["models/gemini-1.5-pro", "models/gemini-1.5-flash"]

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
    doc.add_heading('UNIVERSAL AI REPORT', 0)
    clean_content = re.sub(r'<[^>]+>', '', content) 
    for line in clean_content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- MAIN APP ---
def main():
    st.title("🌌 Universal AI Studio (Deep Dive Edition)")
    if not configure_genai(): return

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🧠 Cấu hình AI")
        with st.spinner("Đang đồng bộ Model..."):
            real_models = get_real_models()
        
        # Logic chọn model thông minh
        model_index = 0
        # Nếu có Pro thì ưu tiên chọn Pro mặc định
        for i, m in enumerate(real_models):
            if "pro" in m: model_index = i; break
            
        model_version = st.selectbox("Engine (Khuyên dùng Pro cho chi tiết):", real_models, index=model_index)

        detail_level = st.select_slider("Độ chi tiết:", options=["Ngắn gọn", "Tiêu chuẩn", "Chi tiết sâu (Deep Dive)"], value="Tiêu chuẩn")

        st.divider()
        st.header("🛠️ KHO VŨ KHÍ")
        
        st.markdown("### 1. Phân tích Cốt lõi")
        opt_summary = st.checkbox("📝 Tóm tắt & Action Items", True)
        opt_process = st.checkbox("🔄 Trích xuất Quy trình", False)
        opt_prosody = st.checkbox("🎭 Phân tích Cảm xúc", False)
        opt_gossip = st.checkbox("☕ Chế độ 'Bà tám'", False)

        st.markdown("### 2. Sáng tạo Nghe/Nhìn")
        opt_audio_script = st.checkbox("🎙️ Podcast Script", False)
        opt_video_script = st.checkbox("🎬 Video Script", False)
        opt_mindmap = st.checkbox("🧠 Mindmap (Sơ đồ tư duy)", True)

        st.markdown("### 3. Học tập & Nghiên cứu")
        opt_report = st.checkbox("📑 Báo cáo chuyên sâu", False)
        opt_briefing = st.checkbox("📄 Briefing Doc", False)
        opt_timeline = st.checkbox("⏳ Timeline", False)
        opt_quiz = st.checkbox("❓ Quiz & Flashcards", False)
        
        st.markdown("### 4. Dữ liệu")
        opt_infographic = st.checkbox("📊 Infographic Data", False)
        opt_slides = st.checkbox("🖥️ Slide Outline", False)
        opt_table = st.checkbox("📉 Data Table", False)

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
            uploaded_files = st.file_uploader("Chọn file (Audio, PDF, Text...)", type=['mp3', 'wav', 'm4a', 'pdf', 'txt', 'md', 'csv'], accept_multiple_files=True)
        
        with col_rec:
            st.subheader("2. Ghi âm trực tiếp")
            audio_bytes = audio_recorder()

        if st.button("🔥 KÍCH HOẠT PHÂN TÍCH", type="primary"):
            temp_paths = []
            if uploaded_files:
                for up_file in uploaded_files:
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
                with st.spinner(f"Đang xử lý sâu với {model_version}... (Có thể mất 1-2 phút)"):
                    try:
                        gemini_files_objs = []
                        for path in temp_paths:
                            g_file = upload_to_gemini(path)
                            gemini_files_objs.append(g_file)
                            os.remove(path)
                        
                        st.session_state.gemini_files = gemini_files_objs
                        
                        # --- CẤU HÌNH PROMPT NÂNG CAO ---
                        
                        # 1. Chỉ thị độ dài (System Instruction Injection)
                        length_instruction = ""
                        if detail_level == "Ngắn gọn":
                            length_instruction = "Trả lời cực kỳ ngắn gọn, súc tích, gạch đầu dòng."
                        elif detail_level == "Tiêu chuẩn":
                            length_instruction = "Trả lời đầy đủ, cân bằng giữa chi tiết và tổng quan."
                        else: # Deep Dive
                            length_instruction = """
                            YÊU CẦU ĐẶC BIỆT QUAN TRỌNG:
                            - Phải viết RẤT CHI TIẾT, RẤT DÀI cho mỗi mục.
                            - Mở rộng tối đa các ý, trích dẫn nguyên văn lời nói/nội dung trong file.
                            - KHÔNG ĐƯỢC TÓM TẮT SƠ SÀI. Nếu mục nào dài, hãy viết thành nhiều đoạn văn.
                            - Phân tích sâu sắc, đưa ra góc nhìn chuyên gia.
                            """

                        prompt = f"""
                        Bạn là chuyên gia phân tích dữ liệu cấp cao.
                        {length_instruction}
                        
                        QUY TẮC ĐỊNH DẠNG:
                        1. Bắt đầu mỗi mục bằng tiêu đề H2 (##) chính xác.
                        2. KHÔNG dùng thẻ XML.
                        
                        HÃY THỰC HIỆN CÁC MỤC SAU:
                        """
                        
                        if opt_summary: prompt += "\n## 1. TÓM TẮT & ACTION ITEMS\n"
                        if opt_process: prompt += "\n## 2. QUY TRÌNH (PROCESS)\n"
                        if opt_prosody: prompt += "\n## 3. CẢM XÚC & THÁI ĐỘ\n"
                        if opt_gossip: prompt += "\n## 4. GÓC BÀ TÁM (GOSSIP)\n"
                        if opt_audio_script: prompt += "\n## 5. PODCAST SCRIPT\n"
                        if opt_video_script: prompt += "\n## 6. VIDEO SCRIPT\n"
                        if opt_mindmap: prompt += "\n## 7. MINDMAP CODE\n(Chỉ trả về code Mermaid trong block ```mermaid```)\n"
                        if opt_report: prompt += "\n## 8. BÁO CÁO CHUYÊN SÂU\n"
                        if opt_briefing: prompt += "\n## 9. BRIEFING DOC\n"
                        if opt_timeline: prompt += "\n## 10. TIMELINE SỰ KIỆN\n"
                        if opt_quiz: prompt += "\n## 11. QUIZ & FLASHCARDS\n"
                        if opt_infographic: prompt += "\n## 12. DỮ LIỆU INFOGRAPHIC\n"
                        if opt_slides: prompt += "\n## 13. DÀN Ý SLIDE\n"
                        if opt_table: prompt += "\n## 14. BẢNG DỮ LIỆU\n"

                        # --- CẤU HÌNH GENERATION CONFIG (QUAN TRỌNG) ---
                        # Tăng max_output_tokens lên tối đa để không bị cắt
                        generation_config = genai.types.GenerationConfig(
                            max_output_tokens=8192, # Mức cao nhất
                            temperature=0.7 # Đủ sáng tạo để viết dài
                        )

                        model = genai.GenerativeModel(model_version)
                        response = model.generate_content(
                            [prompt] + gemini_files_objs,
                            generation_config=generation_config # Áp dụng cấu hình
                        )
                        
                        st.session_state.analysis_result = response.text
                        st.success("✅ Xử lý xong!")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

        # --- HIỂN THỊ KẾT QUẢ ---
        if st.session_state.analysis_result:
            st.divider()
            full_text = st.session_state.analysis_result
            
            doc = create_docx(full_text)
            doc_io = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(doc_io.name)
            with open(doc_io.name, "rb") as f:
                st.download_button("📥 Tải Báo Cáo (.docx)", f, "Universal_Report.docx", type="primary")
            os.remove(doc_io.name)
            
            st.markdown("### 🔍 KẾT QUẢ CHI TIẾT")
            
            sections = full_text.split("## ")
            for section in sections:
                section = section.strip()
                if not section: continue
                
                lines = section.split("\n")
                title = lines[0].strip()
                content = "\n".join(lines[1:]).strip()
                
                if not content or content.startswith("<"): continue

                if "MINDMAP" in title.upper() or "mermaid" in content:
                    with st.expander(f"🧠 {title}", expanded=True):
                        try:
                            mermaid_code = content.split("```mermaid")[1].split("```")[0]
                            st_mermaid(mermaid_code, height=500)
                            st.code(mermaid_code, language="mermaid")
                        except:
                            st.markdown(content)
                else:
                    with st.expander(f"📌 {title}", expanded=False):
                        st.markdown(content)

    # === TAB 2 ===
    with tab2:
        st.header("💬 Chat với Dữ liệu")
        if not st.session_state.gemini_files:
            st.info("👈 Vui lòng Upload file ở Tab 1 trước.")
        else:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
            if user_input := st.chat_input("Hỏi chi tiết..."):
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"): st.markdown(user_input)
                with st.chat_message("assistant"):
                    with st.spinner("Đang suy nghĩ..."):
                        try:
                            chat_model = genai.GenerativeModel(model_version)
                            response = chat_model.generate_content(
                                st.session_state.gemini_files + 
                                [f"Yêu cầu: Trả lời chi tiết. Câu hỏi: {user_input}"]
                            )
                            st.markdown(response.text)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e: st.error(f"Lỗi chat: {e}")

if __name__ == "__main__":
    main()
