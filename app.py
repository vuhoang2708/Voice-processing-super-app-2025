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
st.set_page_config(page_title="Universal AI Studio (Smart Retry)", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #1e3c72; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
    /* Style cho thông báo lỗi */
    .error-box {padding: 15px; background-color: #ffebee; border: 1px solid #ffcdd2; border-radius: 5px; color: #c62828; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- BIẾN TOÀN CỤC ---
STRICT_RULES = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ. CẤM BỊA NỘI DUNG. TRÍCH DẪN GIỜ [mm:ss]."

# --- QUẢN LÝ SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""
# Biến kiểm soát trạng thái lỗi Quota
if "quota_error_state" not in st.session_state: st.session_state.quota_error_state = False
if "current_prompt" not in st.session_state: st.session_state.current_prompt = ""
if "current_config" not in st.session_state: st.session_state.current_config = None

# --- HÀM HỖ TRỢ ---
def get_system_key():
    """Lấy key từ Secrets"""
    try:
        if "SYSTEM_KEYS" in st.secrets:
            keys = st.secrets["SYSTEM_KEYS"]
            if isinstance(keys, str): 
                keys = [k.strip() for k in keys.replace('[','').replace(']','').replace('"','').replace("'",'').split(',')]
            return random.choice(keys)
        elif "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except: return None
    return None

def configure_genai(specific_key=None):
    # Nếu có key cụ thể (do người dùng nhập lúc lỗi) thì dùng luôn
    api_key = specific_key if specific_key else get_system_key()
    
    if not api_key: return False
    try:
        genai.configure(api_key=api_key)
        return True
    except: return False

def get_optimized_models():
    try:
        models = genai.list_models()
        valid = [m.name for m in models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        # Ưu tiên 3.0 Flash Preview
        priority = ["gemini-3-flash-preview", "gemini-2.0-flash-exp", "gemini-1.5-flash"]
        final_list = []
        for p in priority:
            found = [m for m in valid if p in m]
            for f in found:
                if f not in final_list: final_list.append(f)
        for v in valid:
            if v not in final_list: final_list.append(v)
        return final_list if final_list else ["models/gemini-1.5-flash"]
    except: return ["models/gemini-1.5-flash"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def create_docx(content):
    doc = Document()
    doc.add_heading('BÁO CÁO PHÂN TÍCH AI', 0)
    clean_content = re.sub(r'<[^>]+>', '', content)
    for line in clean_content.split('\n'):
        if line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
        elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
        elif line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
        else: doc.add_paragraph(line)
    return doc

# --- MAIN APP ---
def main():
    st.title("🛡️ Universal AI Studio (Smart Retry)")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🛠️ KHO VŨ KHÍ")
        main_mode = st.radio("Mục tiêu chính:", ("📝 Gỡ băng nguyên văn", "📊 Phân tích chuyên sâu"))
        
        if main_mode == "📊 Phân tích chuyên sâu":
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
            # Chỉ dùng để nhập key ban đầu, không dùng cho xử lý lỗi
            initial_key = st.text_input("Key cá nhân (Tùy chọn):", type="password")
            if configure_genai(initial_key):
                st.success("Đã kết nối!")
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")
            else: st.error("Chưa kết nối API!")

        if st.button("🗑️ Reset"): st.session_state.clear(); st.rerun()

    # --- XỬ LÝ LỖI QUOTA (HIỆN LÊN ĐẦU NẾU CÓ LỖI) ---
    if st.session_state.quota_error_state:
        st.markdown("""
        <div class="error-box">
            <h3>⚠️ HẾT HẠN MỨC (QUOTA EXCEEDED)</h3>
            <p>Model hiện tại đang bị Google giới hạn. Bạn có 2 lựa chọn:</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_retry, col_skip = st.columns(2)
        
        with col_retry:
            rescue_key = st.text_input("🔑 Nhập API Key riêng của bạn để tiếp tục dùng Model xịn:", type="password", key="rescue_key")
            if st.button("🚀 Thử lại với Key này"):
                if rescue_key:
                    if configure_genai(rescue_key):
                        st.session_state.quota_error_state = False # Tắt lỗi
                        # Chạy lại lệnh cũ với key mới
                        with st.spinner("Đang chạy lại với Key mới..."):
                            try:
                                model = genai.GenerativeModel(model_version)
                                response = model.generate_content([st.session_state.current_prompt] + st.session_state.gemini_files, generation_config=st.session_state.current_config)
                                st.session_state.analysis_result = response.text
                                st.rerun()
                            except Exception as e:
                                st.error(f"Vẫn lỗi: {e}")
                    else:
                        st.error("Key không hợp lệ.")
                else:
                    st.warning("Vui lòng nhập Key.")

        with col_skip:
            st.write("Hoặc:")
            if st.button("⬇️ Bỏ qua & Dùng Model thấp hơn (1.5 Flash)"):
                st.session_state.quota_error_state = False # Tắt lỗi
                with st.spinner("Đang chuyển sang Gemini 1.5 Flash..."):
                    try:
                        # Cưỡng ép dùng 1.5 Flash
                        fallback_model = genai.GenerativeModel("models/gemini-1.5-flash")
                        response = fallback_model.generate_content([st.session_state.current_prompt] + st.session_state.gemini_files, generation_config=st.session_state.current_config)
                        st.session_state.analysis_result = response.text
                        st.success("Đã xử lý xong bằng Gemini 1.5 Flash!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi hệ thống: {e}")
        
        st.divider() # Ngăn cách với phần dưới

    # --- TABS CHÍNH ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý", "💬 Chat"])

    with tab_work:
        # Chỉ hiện nút Upload khi KHÔNG có lỗi
        if not st.session_state.quota_error_state:
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
                            
                            gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2, top_p=0.95)
                            
                            if main_mode.startswith("📝"):
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Gỡ băng NGUYÊN VĂN 100%. Không tóm tắt. Định danh là 'Diễn giả'."
                            else:
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Phân tích sâu {detail_level}:\n"
                                if opt_summary: prompt += "## TÓM TẮT\n"
                                if opt_action: prompt += "## HÀNH ĐỘNG\n"
                                if opt_process: prompt += "## QUY TRÌNH\n"
                                if opt_prosody: prompt += "## CẢM XÚC\n"
                                if opt_mindmap: prompt += "## MÃ SƠ ĐỒ (Mermaid)\n"
                                if opt_quiz: prompt += "## QUIZ\n"

                            # LƯU LẠI TRẠNG THÁI ĐỂ RETRY NẾU CẦN
                            st.session_state.current_prompt = prompt
                            st.session_state.current_config = gen_config

                            model = genai.GenerativeModel(model_version)
                            response = model.generate_content([prompt] + g_files, generation_config=gen_config)
                            st.session_state.analysis_result = response.text
                            st.success("✅ Hoàn thành.")
                        
                        except Exception as e:
                            # BẮT LỖI QUOTA TẠI ĐÂY
                            if "429" in str(e) or "Quota" in str(e):
                                st.session_state.quota_error_state = True
                                st.rerun() # Tải lại để hiện bảng nhập Key
                            else:
                                st.error(f"Lỗi: {e}")
                else: st.warning("Chưa có file!")

        # HIỂN THỊ KẾT QUẢ
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

            if main_mode.startswith("📝") and st.button("⏭️ Viết tiếp đoạn sau"):
                with st.spinner("Đang nghe tiếp..."):
                    try:
                        cont_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2)
                        model = genai.GenerativeModel(model_version)
                        last_part = res[-300:]
                        c_prompt = f"{STRICT_RULES}\nBạn đã viết đến: '{last_part}'. Hãy viết tiếp NGUYÊN VĂN đoạn sau."
                        
                        # Lưu trạng thái cho nút tiếp tục (đề phòng lỗi quota ở đây)
                        st.session_state.current_prompt = c_prompt
                        st.session_state.current_config = cont_config

                        c_res = model.generate_content([c_prompt] + st.session_state.gemini_files, generation_config=cont_config)
                        st.session_state.analysis_result += "\n\n(TIẾP THEO)\n\n" + c_res.text
                        st.rerun()
                    except Exception as e:
                        if "429" in str(e):
                            st.session_state.quota_error_state = True
                            st.rerun()
                        else: st.error(f"Lỗi: {e}")

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
                        r = m.generate_content(st.session_state.gemini_files + [f"TRẢ LỜI TỪ FILE: {inp}"])
                        st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
                    except Exception as e:
                        if "429" in str(e): st.error("Hết Quota! Vui lòng nhập Key ở Tab bên cạnh.")
                        else: st.error(f"Lỗi: {e}")
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
