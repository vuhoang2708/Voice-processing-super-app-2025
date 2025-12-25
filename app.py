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
from collections import Counter

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio (Smart Retry)", page_icon="🧠", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #1e3c72; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
    div[data-testid="stButton"] > button:contains("DỪNG") {background-color: #d32f2f !important;}
</style>
""", unsafe_allow_html=True)

# --- BIẾN TOÀN CỤC ---
STRICT_RULES = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ. CẤM BỊA NỘI DUNG. TRÍCH DẪN GIỜ [mm:ss]."

# --- QUẢN LÝ SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""
if "is_auto_running" not in st.session_state: st.session_state.is_auto_running = False
if "loop_count" not in st.session_state: st.session_state.loop_count = 0

# --- HÀM HỖ TRỢ ---
def configure_genai(user_key=None):
    api_key = user_key or st.secrets.get("GOOGLE_API_KEY") or (random.choice(st.secrets["SYSTEM_KEYS"]) if "SYSTEM_KEYS" in st.secrets else None)
    if not api_key: return False
    try:
        genai.configure(api_key=api_key)
        return True
    except: return False

def get_optimized_models():
    try:
        models = genai.list_models()
        valid = [m.name for m in models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
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

def check_is_looping(text):
    """Hàm phát hiện AI bị kẹt đĩa (Lặp lại 1 câu quá nhiều lần)"""
    if not text: return False
    lines = text.split('\n')
    # Nếu 1 dòng xuất hiện quá 5 lần -> Nghi vấn lặp
    if len(lines) > 10:
        counts = Counter([line.strip() for line in lines if len(line.strip()) > 10])
        if any(c > 5 for c in counts.values()): return True
    # Nếu 1 cụm từ ngắn lặp lại liên tục (VD: Forum ấy Forum ấy)
    if len(text) > 500:
        sample = text[-500:]
        words = sample.split()
        if len(words) > 20 and len(set(words)) < 5: return True
    return False

def generate_with_smart_retry(model_name, prompt, files, base_temp=0.1):
    """Cơ chế thử lại thông minh: Tăng nhiệt độ nếu bị lặp"""
    attempts = 0
    max_attempts = 3
    current_temp = base_temp
    
    while attempts < max_attempts:
        try:
            # Cấu hình nhiệt độ động
            config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=current_temp)
            model = genai.GenerativeModel(model_name)
            
            response = model.generate_content([prompt] + files, generation_config=config)
            text = response.text
            
            # Kiểm tra xem có bị lặp không
            if check_is_looping(text):
                st.toast(f"⚠️ Phát hiện lặp từ (Temp {current_temp}). Đang thử lại với độ sáng tạo cao hơn...", icon="🔄")
                current_temp += 0.2 # Tăng nhiệt độ để thoát lặp
                attempts += 1
                continue
            
            return text # Nếu ngon thì trả về luôn
            
        except Exception as e:
            if "429" in str(e): # Lỗi Quota thì thử model khác (Fallback)
                st.toast("⚠️ Model quá tải, đang chuyển sang dự phòng...", icon="🔀")
                return generate_with_fallback_model(prompt, files)
            else:
                st.error(f"Lỗi: {e}")
                return None
    
    return text # Trả về kết quả tốt nhất có thể sau 3 lần thử

def generate_with_fallback_model(prompt, files):
    """Hàm phụ: Chạy model dự phòng (1.5 Flash)"""
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        res = model.generate_content([prompt] + files)
        return res.text
    except: return "Lỗi hệ thống: Không thể xử lý."

# --- MAIN APP ---
def main():
    st.title("🛡️ Universal AI Studio (Smart Retry)")
    
    with st.sidebar:
        st.header("🎯 CHẾ ĐỘ HOẠT ĐỘNG")
        main_mode = st.radio("Mục tiêu chính:", ("📝 Gỡ băng nguyên văn", "📊 Phân tích chuyên sâu"))
        
        if main_mode == "📊 Phân tích chuyên sâu":
            st.subheader("CHỌN VŨ KHÍ:")
            opt_summary = st.checkbox("📋 Tóm tắt nội dung", True)
            opt_action = st.checkbox("✅ Danh sách Hành động", True)
            opt_process = st.checkbox("🔄 Trích xuất Quy trình", False)
            opt_prosody = st.checkbox("🎭 Phân tích Cảm xúc", False)
            opt_mindmap = st.checkbox("🧠 Vẽ Sơ đồ tư duy", True)
            opt_quiz = st.checkbox("❓ Câu hỏi Trắc nghiệm", False)
            opt_slides = st.checkbox("🖥️ Dàn ý Slide", False)
        else:
            st.info("💡 Chế độ Gỡ băng sẽ tự động chạy nối tiếp khi hết token.")
            auto_continue = st.checkbox("Tự động nối đoạn (Auto-Continue)", value=True)
        
        st.divider()
        with st.expander("⚙️ Cấu hình & Key"):
            user_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối!")
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
                if main_mode.startswith("📊"):
                    detail_level = st.select_slider("Độ chi tiết:", ["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")
            else: st.error("Chưa kết nối!")

        if st.button("🗑️ Reset App"):
            st.session_state.clear(); st.rerun()

    # --- TABS ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý Dữ liệu", "💬 Chat"])

    with tab_work:
        if not st.session_state.is_auto_running:
            up_files = st.file_uploader("Upload file", accept_multiple_files=True)
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
                
                if not temp_paths:
                    st.warning("Chưa có file!")
                else:
                    with st.spinner(f"Đang xử lý (Cơ chế Smart Retry đang bật)..."):
                        try:
                            g_files = [upload_to_gemini(p) for p in temp_paths]
                            st.session_state.gemini_files = g_files
                            
                            if main_mode.startswith("📝"):
                                prompt = f"""
                                {STRICT_RULES}
                                NHIỆM VỤ: Gỡ băng NGUYÊN VĂN 100%.
                                YÊU CẦU:
                                - Cố gắng nghe kỹ từng từ.
                                - Nếu gặp đoạn nhiễu/lặp: Hãy thử phân tích lại. Nếu vẫn không được thì ghi [ĐOẠN NHIỄU - KHÔNG RÕ] rồi đi tiếp.
                                - KHÔNG ĐƯỢC BỎ QUA NGAY LẬP TỨC.
                                - Định danh: 'Diễn giả'.
                                """
                                if auto_continue:
                                    st.session_state.is_auto_running = True
                                    st.session_state.loop_count = 1
                                
                                # GỌI HÀM SMART RETRY (Temp bắt đầu từ 0.1)
                                res_text = generate_with_smart_retry(model_version, prompt, g_files, base_temp=0.1)
                            else:
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Phân tích sâu {detail_level} cho các mục:\n"
                                if opt_summary: prompt += "## 1. TÓM TẮT CHI TIẾT\n"
                                if opt_action: prompt += "## 2. HÀNH ĐỘNG CẦN LÀM\n"
                                if opt_process: prompt += "## 3. QUY TRÌNH CHI TIẾT\n"
                                if opt_prosody: prompt += "## 4. PHÂN TÍCH CẢM XÚC\n"
                                if opt_mindmap: prompt += "## 5. MÃ SƠ ĐỒ TƯ DUY (Mermaid)\n"
                                if opt_quiz: prompt += "## 6. CÂU HỎI TRẮC NGHIỆM\n"
                                if opt_slides: prompt += "## 7. DÀN Ý SLIDE\n"
                                
                                # Phân tích thì Temp cao hơn chút (0.3)
                                res_text = generate_with_smart_retry(model_version, prompt, g_files, base_temp=0.3)

                            st.session_state.analysis_result = res_text
                            st.rerun()
                        except Exception as e: st.error(f"Lỗi: {e}")

        # --- HIỂN THỊ KẾT QUẢ ---
        if st.session_state.analysis_result:
            if st.session_state.is_auto_running:
                st.warning(f"🔄 Đang tự động gỡ băng đoạn tiếp theo (Vòng lặp #{st.session_state.loop_count})...")
                if st.button("🛑 DỪNG LẠI NGAY"):
                    st.session_state.is_auto_running = False
                    st.success("Đã dừng.")
                    st.rerun()

            st.divider()
            res = st.session_state.analysis_result
            
            # Hiển thị (Lọc rác)
            clean_res = "\n".join([line for line in res.split('\n') if not line.strip().startswith(('*', 'Wait,', 'Refining', 'Final check', 'Constraint'))])
            
            sections = clean_res.split("## ")
            for s in sections:
                if not s.strip(): continue
                lines = s.split("\n")
                with st.expander(f"📌 {lines[0].strip()}", expanded=True):
                    st.markdown("\n".join(lines[1:]))
            
            # Download
            doc = create_docx(res)
            doc_io = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(doc_io.name)
            with open(doc_io.name, "rb") as f:
                st.download_button("📥 Tải Báo Cáo (.docx)", f, "Bao_Cao_AI.docx", type="primary")
            os.remove(doc_io.name)

            # --- LOGIC AUTO-CONTINUE (GỠ BĂNG) ---
            if st.session_state.is_auto_running and main_mode.startswith("📝"):
                st.divider()
                placeholder = st.empty()
                for i in range(3, 0, -1):
                    placeholder.info(f"⏳ Chuẩn bị nối đoạn tiếp theo trong {i} giây...")
                    time.sleep(1)
                placeholder.empty()
                
                with st.spinner(f"🤖 AI đang nghe tiếp đoạn {st.session_state.loop_count + 1}..."):
                    try:
                        last_part = res[-500:] 
                        c_prompt = f"""
                        CONTEXT: Bạn đang gỡ băng dở dang file âm thanh này.
                        MỎ NEO (Đoạn cuối cùng bạn vừa viết): "...{last_part}"
                        NHIỆM VỤ: Tìm vị trí MỎ NEO, viết tiếp NGUYÊN VĂN đoạn sau. KHÔNG viết lại mỏ neo.
                        """
                        
                        # Dùng Smart Retry cho cả đoạn nối tiếp
                        c_res_text = generate_with_smart_retry(model_version, c_prompt, st.session_state.gemini_files, base_temp=0.1)
                        
                        if not c_res_text or len(c_res_text) < 50 or "kết thúc" in c_res_text.lower():
                            st.session_state.is_auto_running = False
                            st.success("✅ Đã gỡ băng xong toàn bộ file!")
                        else:
                            st.session_state.analysis_result += "\n\n" + c_res_text
                            st.session_state.loop_count += 1
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Lỗi hoặc đã hết file: {e}")
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
                        m_chat = genai.GenerativeModel(model_version)
                        r = m_chat.generate_content(st.session_state.gemini_files + [f"Trả lời từ file: {inp}"])
                        st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
                    except Exception as e: st.error(f"Lỗi: {e}")
        else: st.info("👈 Upload file trước.")

if __name__ == "__main__":
    main()
