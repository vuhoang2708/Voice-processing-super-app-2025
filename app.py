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
st.set_page_config(page_title="Universal AI Studio Pro", page_icon="🚀", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: linear-gradient(to right, #1e3c72, #2a5298); color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {font-size: 1.2rem !important; color: #1e3c72; border-bottom: 2px solid #eee; padding-bottom: 5px;}
    .stRadio > label {font-weight: bold; color: #d32f2f;}
</style>
""", unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""

# --- HÀM HỖ TRỢ ---
def configure_genai(user_key=None):
    api_key = None
    if user_key:
        api_key = user_key
    else:
        try:
            if "SYSTEM_KEYS" in st.secrets:
                system_keys = st.secrets["SYSTEM_KEYS"]
                if isinstance(system_keys, str): 
                    clean_str = system_keys.replace('[','').replace(']','').replace('"','').replace("'",'')
                    system_keys = [k.strip() for k in clean_str.split(',') if k.strip()]
                if system_keys: api_key = random.choice(system_keys)
            elif "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]
        except: pass
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
        # Ưu tiên Flash 3.0/2.0 Preview lên đầu
        for keyword in ["gemini-3.0-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash"]:
            found = next((m for m in valid_list if keyword in m), None)
            if found:
                valid_list.insert(0, valid_list.pop(valid_list.index(found)))
                break
        return valid_list
    except:
        return ["models/gemini-1.5-flash"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def create_docx(content):
    doc = Document()
    doc.add_heading('BÁO CÁO PHÂN TÍCH AI CHUYÊN NGHIỆP', 0)
    clean_content = re.sub(r'<[^>]+>', '', content)
    for line in clean_content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- MAIN APP ---
def main():
    st.title("🌌 Universal AI Studio (Pro Mode)")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🎯 CHẾ ĐỘ HOẠT ĐỘNG")
        
        # SỬ DỤNG RADIO BUTTON ĐỂ TÁCH BIỆT NHIỆM VỤ
        main_mode = st.radio(
            "Chọn mục tiêu chính của bạn:",
            ("📝 Gỡ băng nguyên văn (Full Transcript)", "📊 Bộ vũ khí phân tích (Deep Analysis)"),
            help="Lưu ý: Chế độ Gỡ băng sẽ ưu tiên chép lời chính xác nhất. Chế độ Phân tích sẽ dùng các công cụ chuyên sâu."
        )

        st.divider()

        if main_mode == "📊 Bộ vũ khí phân tích (Deep Analysis)":
            st.subheader("🛠️ CHỌN CÁC VŨ KHÍ PHÂN TÍCH")
            col_a, col_b = st.columns(2)
            with col_a:
                opt_summary = st.checkbox("📋 Tóm tắt ý", True)
                opt_action = st.checkbox("✅ Hành động", True)
                opt_process = st.checkbox("🔄 Quy trình", False)
                opt_prosody = st.checkbox("🎭 Cảm xúc", False)
            with col_b:
                opt_gossip = st.checkbox("☕ Bà tám", False)
                opt_mindmap = st.checkbox("🧠 Mindmap", True)
                opt_quiz = st.checkbox("❓ Trắc nghiệm", False)
                opt_slides = st.checkbox("🖥️ Dàn ý Slide", False)
        else:
            st.info("💡 Chế độ Gỡ băng sẽ tự động tắt các tính năng phân tích để đảm bảo độ dài và độ chính xác của văn bản.")

        st.divider()
        
        # CẤU HÌNH XUỐNG ĐÁY
        with st.expander("⚙️ Cấu hình & API Key (Nâng cao)"):
            user_api_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_api_key):
                st.success("Đã kết nối!")
                real_models = get_real_models()
                model_version = st.selectbox("Chọn Engine (Mặc định Flash 3/2):", real_models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Chi tiết sâu"], value="Chi tiết sâu")
            else:
                st.error("Chưa kết nối!")
                model_version = "models/gemini-1.5-flash"
                detail_level = "Tiêu chuẩn"

        if st.button("🗑️ Reset App"):
            st.session_state.clear()
            st.rerun()

    # --- GIAO DIỆN CHÍNH ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý Dữ liệu", "💬 Chat Chuyên sâu"])

    with tab_work:
        col1, col2 = st.columns(2)
        with col1: uploaded_files = st.file_uploader("Upload file (Audio, PDF, Text...)", type=['mp3', 'wav', 'm4a', 'pdf', 'txt', 'md', 'csv'], accept_multiple_files=True)
        with col2: audio_bytes = audio_recorder()

        if st.button("🚀 BẮT ĐẦU THỰC THI", type="primary"):
            temp_paths = []
            if uploaded_files:
                for up_file in uploaded_files:
                    file_ext = os.path.splitext(up_file.name)[1] or ".txt"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                        tmp.write(up_file.getvalue())
                        temp_paths.append(tmp.name)
            if audio_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes)
                    temp_paths.append(tmp.name)
            
            if not temp_paths:
                st.warning("Vui lòng cung cấp dữ liệu đầu vào!")
            else:
                with st.spinner(f"AI đang thực hiện chế độ: {main_mode}..."):
                    try:
                        gemini_files_objs = []
                        for path in temp_paths:
                            g_file = upload_to_gemini(path)
                            gemini_files_objs.append(g_file)
                            os.remove(path)
                        
                        st.session_state.gemini_files = gemini_files_objs

                        # --- LOGIC PROMPT BIẾN THIÊN ---
                        if main_mode == "📝 Gỡ băng nguyên văn (Full Transcript)":
                            prompt = """
                            BẠN LÀ THƯ KÝ TÒA ÁN CHUYÊN NGHIỆP. 
                            NHIỆM VỤ TỐI THƯỢNG: Nghe và chép lại NGUYÊN VĂN (Verbatim) từng lời nói trong file âm thanh/tài liệu.
                            YÊU CẦU:
                            - KHÔNG ĐƯỢC TÓM TẮT.
                            - KHÔNG ĐƯỢC BỎ SÓT các câu chuyện kể, ví dụ, lời đùa hay dẫn chứng.
                            - Ghi rõ tên người nói (nếu nhận diện được) và mốc thời gian [phút:giây].
                            - Sử dụng 100% Tiếng Việt chuẩn.
                            - Viết dài và chi tiết nhất có thể.
                            Bắt đầu bằng tiêu đề: ## 0. BẢN GỠ BĂNG CHI TIẾT
                            """
                        else:
                            prompt = f"Bạn là chuyên gia phân tích dữ liệu. Hãy thực hiện các mục sau (Độ chi tiết: {detail_level}):\n"
                            if opt_summary: prompt += "## 1. TÓM TẮT Ý CHÍNH\n"
                            if opt_action: prompt += "## 2. DANH SÁCH HÀNH ĐỘNG (ACTION ITEMS)\n"
                            if opt_process: prompt += "## 3. QUY TRÌNH THỰC HIỆN\n"
                            if opt_prosody: prompt += "## 4. PHÂN TÍCH TÂM LÝ & NGỮ ĐIỆU\n"
                            if opt_gossip: prompt += "## 5. GÓC BÀ TÁM (CHUYỆN BÊN LỀ)\n"
                            if opt_mindmap: prompt += "## 6. MÃ SƠ ĐỒ TƯ DUY\n(Chỉ trả về code mermaid trong block ```mermaid```)\n"
                            if opt_quiz: prompt += "## 7. CÂU HỎI KIỂM TRA & THẺ NHỚ\n"
                            if opt_slides: prompt += "## 8. DÀN Ý BÀI THUYẾT TRÌNH\n"

                        model = genai.GenerativeModel(model_version)
                        # Tăng giới hạn tối đa cho bản gỡ băng
                        config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.3)
                        response = model.generate_content([prompt] + gemini_files_objs, generation_config=config)
                        
                        st.session_state.analysis_result = response.text
                        st.success("✅ Đã hoàn thành!")
                    except Exception as e:
                        st.error(f"Lỗi hệ thống: {e}")

        if st.session_state.analysis_result:
            st.divider()
            full_text = st.session_state.analysis_result
            
            # Tải về
            doc = create_docx(full_text)
            doc_io = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(doc_io.name)
            with open(doc_io.name, "rb") as f:
                st.download_button("📥 Tải Báo Cáo (.docx)", f, "Bao_Cao_AI_Pro.docx", type="primary")
            os.remove(doc_io.name)
            
            # Hiển thị
            sections = full_text.split("## ")
            for section in sections:
                if not section.strip(): continue
                lines = section.split("\n")
                title = lines[0].strip()
                content = "\n".join(lines[1:]).strip()
                if not content or content.startswith("<"): continue

                if "MERMAID" in title.upper() or "SƠ ĐỒ" in title.upper():
                    with st.expander(f"🧠 {title}", expanded=True):
                        try:
                            mermaid_code = content.split("```mermaid")[1].split("```")[0]
                            st_mermaid(mermaid_code, height=500)
                        except: st.markdown(content)
                else:
                    with st.expander(f"📌 {title}", expanded=True if main_mode.startswith("📝") else False):
                        st.markdown(content)

    with tab_chat:
        st.header("💬 Chat với Dữ liệu")
        if not st.session_state.gemini_files:
            st.info("👈 Upload file ở Tab 1 trước.")
        else:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
            if user_input := st.chat_input("Hỏi chi tiết về nội dung..."):
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"): st.markdown(user_input)
                with st.chat_message("assistant"):
                    with st.spinner("Đang trả lời..."):
                        try:
                            chat_model = genai.GenerativeModel(model_version)
                            response = chat_model.generate_content(st.session_state.gemini_files + [f"Trả lời Tiếng Việt: {user_input}"])
                            st.markdown(response.text)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e: st.error(f"Lỗi: {e}")

if __name__ == "__main__":
    main()
