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
st.set_page_config(page_title="AI Studio Pro - No Guessing", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #c31432; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
</style>
""", unsafe_allow_html=True)

# --- QUẢN LÝ SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""

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
        order = ["gemini-3.0-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
        final_list = []
        for target in order:
            for v in valid:
                if target in v and v not in final_list and "lite" not in v:
                    final_list.append(v)
        return final_list
    except: return ["models/gemini-1.5-flash"]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

# --- MAIN APP ---
def main():
    st.title("🛡️ Universal AI Studio (Cơ chế Chống Bịa tên)")
    
    with st.sidebar:
        st.header("🛠️ KHO VŨ KHÍ")
        main_mode = st.radio("Mục tiêu chính:", ("📝 Gỡ băng nguyên văn", "📊 Phân tích chuyên sâu"))
        st.divider()
        with st.expander("⚙️ Cấu hình"):
            user_key = st.text_input("Nhập Key riêng:", type="password")
            if configure_genai(user_key):
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
                detail_level = st.select_slider("Độ chi tiết:", options=["Sơ lược", "Tiêu chuẩn", "Sâu"], value="Sâu")
        if st.button("🗑️ Reset"): st.session_state.clear(); st.rerun()

    tab_work, tab_chat = st.tabs(["📂 Xử lý", "💬 Chat"])

    with tab_work:
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
                with st.spinner("Đang thực hiện 'Strict Grounding' - Chống bịa đặt dữ liệu..."):
                    try:
                        g_files = [upload_to_gemini(p) for p in temp_paths]
                        st.session_state.gemini_files = g_files
                        
                        # CẤU HÌNH KỶ LUẬT
                        config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.1, top_p=0.9)
                        
                        # PROMPT CỰC GẮT ĐỂ DIỆT TRỪ ÁO GIÁC TÊN
                        anti_hallucination_rules = """
                        QUY TẮC AN NINH DỮ LIỆU (BẮT BUỘC):
                        1. CẤM ĐOÁN TÊN: Tuyệt đối không sử dụng kiến thức bên ngoài để gán nhãn tên cho người nói. 
                        2. ĐỊNH DANH MẶC ĐỊNH: Luôn gọi người nói là 'Người nói 1', 'Người nói 2' hoặc 'Diễn giả'.
                        3. ĐIỀU KIỆN THAY ĐỔI TÊN: Chỉ được ghi tên thật của người nói nếu và chỉ nếu họ tự phát âm chính xác câu: 'Tên tôi là [Tên]' hoặc 'Tôi là [Tên]' trong file ghi âm này. Nếu không nghe thấy câu này, việc điền tên bị coi là vi phạm đạo đức dữ liệu.
                        4. CẤM BỊA NỘI DUNG: Không tự ý thêm thắt các chi tiết không có trong file âm thanh. Nếu file bị rè hoặc thiếu thông tin, hãy ghi '[Âm thanh không rõ]'.
                        5. TRÍCH DẪN GIỜ: Luôn ghi mốc thời gian [phút:giây] ở đầu mỗi đoạn hội thoại.
                        """

                        if main_mode.startswith("📝"):
                            prompt = f"{anti_hallucination_rules}\nNHIỆM VỤ: Gỡ băng nguyên văn 100%. Viết Tiếng Việt."
                        else:
                            prompt = f"{anti_hallucination_rules}\nNHIỆM VỤ: Phân tích sâu {detail_level} dựa duy nhất trên file gốc."

                        model = genai.GenerativeModel(model_version)
                        response = model.generate_content([prompt] + g_files, generation_config=config)
                        st.session_state.analysis_result = response.text
                        st.success("✅ Đã hoàn thành với cơ chế bảo vệ dữ liệu.")
                    except Exception as e: st.error(f"Lỗi: {e}")
            else: st.warning("Chưa có file!")

        if st.session_state.analysis_result:
            res = st.session_state.analysis_result
            sections = res.split("## ")
            for s in sections:
                if not s.strip(): continue
                lines = s.split("\n")
                with st.expander(f"📌 {lines[0].strip()}", expanded=True):
                    st.markdown("\n".join(lines[1:]))

            if main_mode.startswith("📝") and st.button("⏭️ Viết tiếp đoạn sau"):
                with st.spinner("Đang nghe tiếp..."):
                    try:
                        cont_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.1)
                        model = genai.GenerativeModel(model_version)
                        c_prompt = f"{anti_hallucination_rules}\nTiếp tục gỡ băng đoạn tiếp theo của file. Bắt đầu ngay sau đoạn: '{res[-200:]}'"
                        c_res = model.generate_content([c_prompt] + st.session_state.gemini_files, generation_config=cont_config)
                        st.session_state.analysis_result += "\n\n--- TIẾP THEO ---\n\n" + c_res.text
                        st.rerun()
                    except Exception as e: st.error(f"Lỗi: {e}")

if __name__ == "__main__":
    main()
