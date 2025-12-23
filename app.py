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
st.set_page_config(page_title="Universal AI Studio (Final)", page_icon="🇻🇳", layout="wide")
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

# --- HÀM CẤU HÌNH KEY (FIX LỖI NHẬN DIỆN & PARSE LIST) ---
def configure_genai(user_key=None):
    api_key = None
    
    # 1. Ưu tiên Key người dùng nhập trực tiếp
    if user_key:
        api_key = user_key
        st.toast("🔑 Đang dùng Key cá nhân.")
    else:
        # 2. Tự động tìm Key trong Secrets
        try:
            if "SYSTEM_KEYS" in st.secrets:
                system_keys = st.secrets["SYSTEM_KEYS"]
                # Xử lý nếu người dùng nhập string thay vì list trong secrets
                if isinstance(system_keys, str): 
                    # Loại bỏ ngoặc vuông, ngoặc kép và tách dấu phẩy
                    clean_str = system_keys.replace('[','').replace(']','').replace('"','').replace("'",'')
                    system_keys = [k.strip() for k in clean_str.split(',') if k.strip()]
                
                if system_keys:
                    api_key = random.choice(system_keys)
            elif "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]
            
            if not api_key:
                raise Exception("Empty Key List")
                
        except Exception as e:
            st.error(f"🚨 Lỗi cấu hình Key: {e}. Vui lòng nhập Key cá nhân.")
            return False

    # 3. Thử kết nối
    try:
        genai.configure(api_key=api_key)
        return True
    except:
        st.error("❌ API Key không hợp lệ hoặc đã hết hạn mức!")
        return False

def get_real_models():
    try:
        models = genai.list_models()
        valid_list = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                valid_list.append(m.name)
        valid_list.sort(reverse=True) 
        # Ưu tiên Pro
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
    doc.add_heading('BÁO CÁO PHÂN TÍCH AI', 0)
    # Lọc bỏ XML và khoảng trắng thừa
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
    st.title("🇻🇳 Universal AI Studio (Full Option)")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🧠 Cấu hình AI")
        
        with st.expander("🔧 Cài đặt nâng cao (Key dự phòng)"):
            user_api_key = st.text_input("Nhập Key riêng:", type="password")
        
        if not configure_genai(user_api_key): return

        with st.spinner("Đang kết nối..."):
            real_models = get_real_models()
        
        model_index = 0
        for i, m in enumerate(real_models):
            if "pro" in m: model_index = i; break
        model_version = st.selectbox("Engine (Khuyên dùng Pro):", real_models, index=model_index)

        detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Chi tiết sâu"], value="Tiêu chuẩn")

        st.divider()
        st.header("🛠️ CHỌN TÍNH NĂNG")
        
        st.markdown("### 1. Cốt lõi")
        opt_transcript = st.checkbox("📝 Gỡ băng chi tiết (Transcript)", False) 
        opt_summary = st.checkbox("📋 Tóm tắt & Hành động", True)
        opt_process = st.checkbox("🔄 Trích xuất Quy trình", False)
        opt_prosody = st.checkbox("🎭 Phân tích Thái độ", False)
        opt_gossip = st.checkbox("☕ Chế độ 'Bà tám'", False)

        st.markdown("### 2. Sáng tạo")
        opt_audio_script = st.checkbox("🎙️ Kịch bản Podcast", False)
        opt_video_script = st.checkbox("🎬 Kịch bản Video", False)
        opt_mindmap = st.checkbox("🧠 Sơ đồ tư duy (Mindmap)", True)

        st.markdown("### 3. Nghiên cứu")
        opt_report = st.checkbox("📑 Báo cáo chuyên sâu", False)
        opt_briefing = st.checkbox("📄 Tài liệu tóm lược", False)
        opt_timeline = st.checkbox("⏳ Dòng thời gian", False)
        opt_quiz = st.checkbox("❓ Trắc nghiệm & Thẻ nhớ", False)
        
        st.markdown("### 4. Dữ liệu")
        opt_infographic = st.checkbox("📊 Dữ liệu Infographic", False)
        opt_slides = st.checkbox("🖥️ Dàn ý Slide", False)
        opt_table = st.checkbox("📉 Bảng số liệu", False)

        st.divider()
        if st.button("🗑️ Làm mới (Reset)"):
            st.session_state.clear()
            st.rerun()

    # --- GIAO DIỆN TAB ---
    tab1, tab2 = st.tabs(["📂 Upload & Phân tích", "💬 Chat Tiếng Việt"])

    # === TAB 1 ===
    with tab1:
        col_up, col_rec = st.columns(2)
        files_to_process = []
        
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
                        tmp.write(up_file.getvalue())
                        temp_paths.append(tmp.name)
            
            if audio_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes)
                    temp_paths.append(tmp.name)
            
            if not temp_paths:
                st.warning("Vui lòng chọn file hoặc ghi âm!")
            else:
                with st.spinner(f"Đang xử lý {len(temp_paths)} file... (Chế độ: {detail_level})"):
                    try:
                        gemini_files_objs = []
                        for path in temp_paths:
                            g_file = upload_to_gemini(path)
                            gemini_files_objs.append(g_file)
                            os.remove(path)
                        
                        st.session_state.gemini_files = gemini_files_objs
                        
                        # --- PROMPT ---
                        length_instruction = ""
                        if detail_level == "Sơ lược":
                            length_instruction = "Trả lời ngắn gọn, gạch đầu dòng."
                        elif detail_level == "Tiêu chuẩn":
                            length_instruction = "Trả lời đầy đủ các ý chính."
                        else:
                            length_instruction = """
                            YÊU CẦU CHI TIẾT SÂU (DEEP DIVE):
                            - Viết rất chi tiết, dài, mở rộng ý.
                            - Trích dẫn nguyên văn lời nói quan trọng.
                            """

                        prompt = f"""
                        Bạn là chuyên gia phân tích nội dung Tiếng Việt.
                        Nhiệm vụ: Phân tích các file đính kèm và tạo báo cáo.
                        
                        QUY TẮC ĐỊNH DẠNG (BẮT BUỘC TUÂN THỦ):
                        1. Bắt đầu mỗi mục lớn bằng tiêu đề H2 (##) CHÍNH XÁC như danh sách yêu cầu bên dưới.
                        2. TUYỆT ĐỐI KHÔNG dùng H2 (##) cho các mục con bên trong. Hãy dùng H3 (###) hoặc in đậm (**).
                        3. KHÔNG trả về thẻ XML/HTML.
                        4. Nếu thiếu thông tin, ghi: "Không tìm thấy dữ liệu".
                        5. {length_instruction}
                        
                        DANH SÁCH CÁC MỤC CẦN LÀM:
                        """
                        
                        if opt_transcript: prompt += "\n## 0. GỠ BĂNG CHI TIẾT (TRANSCRIPT)\n- Ghi lại toàn bộ nội dung hội thoại, phân biệt người nói (nếu có thể).\n"
                        if opt_summary: prompt += "\n## 1. TÓM TẮT & HÀNH ĐỘNG\n"
                        if opt_process: prompt += "\n## 2. QUY TRÌNH THỰC HIỆN\n"
                        if opt_prosody: prompt += "\n## 3. PHÂN TÍCH CẢM XÚC & THÁI ĐỘ\n"
                        if opt_gossip: prompt += "\n## 4. GÓC BÀ TÁM (CHUYỆN BÊN LỀ)\n"
                        if opt_audio_script: prompt += "\n## 5. KỊCH BẢN PODCAST (ĐỐI THOẠI)\n"
                        if opt_video_script: prompt += "\n## 6. KỊCH BẢN VIDEO\n"
                        if opt_mindmap: prompt += "\n## 7. MÃ SƠ ĐỒ TƯ DUY (MERMAID)\n(Chỉ trả về code trong block ```mermaid```)\n"
                        if opt_report: prompt += "\n## 8. BÁO CÁO CHUYÊN SÂU\n"
                        if opt_briefing: prompt += "\n## 9. TÀI LIỆU TÓM LƯỢC\n"
                        if opt_timeline: prompt += "\n## 10. DÒNG THỜI GIAN SỰ KIỆN\n"
                        if opt_quiz: prompt += "\n## 11. TRẮC NGHIỆM & THẺ NHỚ\n(Dùng H3 cho từng phần, không dùng H2)\n"
                        if opt_infographic: prompt += "\n## 12. DỮ LIỆU ĐỒ HỌA (INFOGRAPHIC)\n"
                        if opt_slides: prompt += "\n## 13. DÀN Ý BÀI THUYẾT TRÌNH\n"
                        if opt_table: prompt += "\n## 14. BẢNG SỐ LIỆU CHI TIẾT\n"

                        generation_config = genai.types.GenerationConfig(
                            max_output_tokens=8192, 
                            temperature=0.5
                        )

                        model = genai.GenerativeModel(model_version)
                        response = model.generate_content(
                            [prompt] + gemini_files_objs,
                            generation_config=generation_config
                        )
                        
                        st.session_state.analysis_result = response.text
                        st.success("✅ Đã phân tích xong!")
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
                st.download_button("📥 Tải Báo Cáo Word (.docx)", f, "Bao_Cao_AI.docx", type="primary")
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

                if "MERMAID" in title.upper() or "SƠ ĐỒ" in title.upper():
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
                                [f"Yêu cầu: Trả lời bằng Tiếng Việt. Câu hỏi: {user_input}"]
                            )
                            st.markdown(response.text)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e: st.error(f"Lỗi chat: {e}")

if __name__ == "__main__":
    main()
