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
import shutil

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Universal AI Studio (Pro)", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background: #1e3c72; color: white;}
    .stExpander {border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff;}
    .stMarkdown h2 {color: #1a2a6c; border-bottom: 2px solid #eee; padding-bottom: 5px;}
    div[data-testid="stButton"] > button:contains("DỪNG") {background-color: #d32f2f !important;}
</style>
""", unsafe_allow_html=True)

# --- 2. BIẾN TOÀN CỤC & CẤU HÌNH ---
STRICT_RULES = "CHỈ DÙNG FILE GỐC. CẤM BỊA TÊN DIỄN GIẢ. CẤM BỊA NỘI DUNG. TRÍCH DẪN GIỜ [mm:ss]."
MAX_LOOPS = 20  # Giới hạn an toàn: khoảng 2 tiếng audio để tránh treo máy

# --- 3. QUẢN LÝ SESSION ---
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gemini_files" not in st.session_state: st.session_state.gemini_files = [] 
if "local_files" not in st.session_state: st.session_state.local_files = [] # Theo dõi file tạm
if "analysis_result" not in st.session_state: st.session_state.analysis_result = ""
if "is_auto_running" not in st.session_state: st.session_state.is_auto_running = False
if "loop_count" not in st.session_state: st.session_state.loop_count = 0

# --- 4. HÀM HỖ TRỢ KỸ THUẬT ---

def cleanup_resources():
    """Dọn dẹp tài nguyên trên Cloud và Local để tiết kiệm bộ nhớ"""
    # 1. Xóa file trên Google Cloud
    if st.session_state.gemini_files:
        for f in st.session_state.gemini_files:
            try:
                genai.delete_file(f.name)
            except Exception: pass
    
    # 2. Xóa file tạm trên ổ cứng server
    if st.session_state.local_files:
        for p in st.session_state.local_files:
            try:
                if os.path.exists(p): os.remove(p)
            except Exception: pass
            
    st.session_state.gemini_files = []
    st.session_state.local_files = []

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

def get_optimized_models():
    # Danh sách cứng: Đã cập nhật theo chỉ đạo của bác
    return [
        "models/gemini-3.0-flash-preview", # Ưu tiên số 1: Model bác đang dùng ngon
        "models/gemini-2.0-flash-exp",    # Bản Flash Next Gen (Experimental)
        "models/gemini-1.5-pro",          # Bản Pro ổn định
        "models/gemini-1.5-flash",        # Bản Backup tiết kiệm
        "models/gemini-1.5-pro-002",      # Bản Pro cập nhật
    ]

def upload_to_gemini(path):
    mime_type, _ = mimetypes.guess_type(path)
    file = genai.upload_file(path, mime_type=mime_type or "application/octet-stream")
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
    return file

def get_smart_anchor(text, char_limit=1000):
    """Lấy mỏ neo thông minh: Cắt đúng dấu chấm câu để AI không bị loạn"""
    anchor = text[-char_limit:]
    # Tìm dấu chấm câu (.!?) hoặc xuống dòng gần nhất
    match = re.search(r'[.!?\n]', anchor)
    if match:
        return anchor[match.start()+1:].strip()
    return anchor # Fallback nếu không tìm thấy

def create_docx(content):
    """Tạo file Word sạch, loại bỏ ký tự Markdown thừa"""
    doc = Document()
    doc.add_heading('BÁO CÁO GỠ BĂNG (AI STUDIO)', 0)
    
    clean_content = content.replace("```markdown", "").replace("```", "")
    
    for line in clean_content.split('\n'):
        # Loại bỏ các ký tự format Markdown cơ bản để văn bản Word đẹp hơn
        clean_text = line.strip().replace('**', '').replace('__', '')
        
        if not clean_text: continue
        
        if line.startswith('# '): 
            doc.add_heading(clean_text.replace('# ', ''), level=1)
        elif line.startswith('## '): 
            doc.add_heading(clean_text.replace('## ', ''), level=2)
        elif line.startswith('### '): 
            doc.add_heading(clean_text.replace('### ', ''), level=3)
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(clean_text[2:], style='List Bullet')
        else:
            doc.add_paragraph(clean_text)
    return doc

# --- 5. HÀM XỬ LÝ KẾT QUẢ AN TOÀN (ANTI-CRASH) ---
def get_safe_response(response):
    """Trích xuất text an toàn, xử lý triệt để lỗi bản quyền (Finish Reason 4)"""
    try:
        if not response.candidates:
            return "\n\n[LỖI: Không có phản hồi từ AI (Candidates Empty)]"
            
        finish_reason = response.candidates[0].finish_reason
        
        # 1: STOP (Thành công), 2: MAX_TOKENS (Hết dung lượng)
        if finish_reason in [1, 2]: 
            return response.text
        
        # 3: SAFETY (Bộ lọc an toàn), 4: RECITATION (Bản quyền)
        elif finish_reason == 3:
            return "\n\n[CẢNH BÁO: Nội dung bị chặn do vi phạm quy tắc an toàn của Google.]"
        elif finish_reason == 4:
            return "\n\n[DỪNG: Phát hiện nội dung có bản quyền/âm nhạc. Google từ chối xử lý tiếp.]"
        
        else:
            return f"\n\n[Lỗi không xác định: Finish Reason {finish_reason}]"
            
    except Exception as e:
        try:
            return response.text # Cố gắng lấy text lần cuối
        except:
            return f"\n\n[Lỗi xử lý phản hồi: {e}]"

# --- 6. GIAO DIỆN CHÍNH (MAIN) ---
def main():
    with st.sidebar:
        st.header("🎯 CHẾ ĐỘ")
        main_mode = st.radio("Mục tiêu:", ("📝 Gỡ băng nguyên văn", "📊 Phân tích chuyên sâu"))
        
        if main_mode == "📊 Phân tích chuyên sâu":
            st.subheader("Tùy chọn output:")
            c1, c2 = st.columns(2)
            with c1:
                st.checkbox("📋 Tóm tắt", True)
                st.checkbox("✅ Hành động", True)
            with c2:
                st.checkbox("🧠 Mindmap", True)
                st.checkbox("❓ Quiz", False)
        else:
            st.info("Chế độ Gỡ băng sẽ tự động chạy nối tiếp.")
            auto_continue = st.checkbox("Tự động nối đoạn (Auto-Loop)", value=True)
        
        st.divider()
        with st.expander("⚙️ Cấu hình & Key"):
            user_key = st.text_input("Key riêng (nếu có):", type="password")
            if configure_genai(user_key):
                st.success("Đã kết nối Gemini!")
                models = get_optimized_models()
                model_version = st.selectbox("Engine:", models, index=0)
            else: st.error("Chưa kết nối!")

        if st.button("🗑️ RESET & DỌN DẸP"):
            cleanup_resources()
            st.session_state.clear()
            st.rerun()

    # --- TABS ---
    tab_work, tab_chat = st.tabs(["📂 Xử lý File", "💬 Chat với AI"])

    with tab_work:
        if not st.session_state.is_auto_running:
            st.info("Hỗ trợ: Video, Âm thanh, PDF, Tài liệu. (Tự động xóa sau khi Reset)")
            up_files = st.file_uploader("Upload file", accept_multiple_files=True)
            audio_bytes = audio_recorder()

            if st.button("🚀 BẮT ĐẦU XỬ LÝ", type="primary"):
                # 1. Lưu file tạm (Local)
                temp_paths = []
                if up_files:
                    for f in up_files:
                        ext = os.path.splitext(f.name)[1] or ".txt"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                            tmp.write(f.getvalue())
                            temp_paths.append(tmp.name)
                if audio_bytes:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        tmp.write(audio_bytes)
                        temp_paths.append(tmp.name)
                
                # Lưu đường dẫn local để xóa sau này
                st.session_state.local_files.extend(temp_paths)

                if not temp_paths:
                    st.warning("Vui lòng chọn file hoặc ghi âm!")
                else:
                    with st.spinner(f"Đang tải lên Gemini ({model_version})..."):
                        try:
                            # 2. Upload lên Gemini Cloud
                            g_files = [upload_to_gemini(p) for p in temp_paths]
                            st.session_state.gemini_files = g_files
                            
                            # Tắt bộ lọc an toàn để tránh lỗi false positive
                            safety_settings = [
                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                            ]
                            
                            gen_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2)

                            # 3. Tạo Prompt ban đầu
                            if main_mode.startswith("📝"):
                                prompt = f"""
                                {STRICT_RULES}
                                NHIỆM VỤ: Gỡ băng NGUYÊN VĂN 100%.
                                YÊU CẦU:
                                1. Bắt đầu mỗi câu bằng [Phút:Giây].
                                2. Viết lại chính xác từng từ, kể cả từ đệm.
                                3. Định danh: 'Diễn giả 1', 'Diễn giả 2' (Không đoán tên thật).
                                """
                                if auto_continue:
                                    st.session_state.is_auto_running = True
                                    st.session_state.loop_count = 1
                            else:
                                prompt = f"{STRICT_RULES}\nNHIỆM VỤ: Phân tích sâu nội dung.\nOUTPUT FORMAT:\n## TÓM TẮT\n## HÀNH ĐỘNG\n## MINDMAP (Mermaid code)\n## QUIZ"

                            # 4. Gọi AI
                            model = genai.GenerativeModel(model_version)
                            response = model.generate_content(
                                [prompt] + g_files, 
                                generation_config=gen_config,
                                safety_settings=safety_settings
                            )
                            
                            safe_text = get_safe_response(response)
                            st.session_state.analysis_result = safe_text
                            st.rerun()
                        except Exception as e: st.error(f"Lỗi khởi tạo: {e}")

        # HIỂN THỊ KẾT QUẢ
        if st.session_state.analysis_result:
            # Logic dừng nếu đang auto-run
            if st.session_state.is_auto_running:
                st.warning(f"🔄 Đang tự động nối đoạn (Vòng {st.session_state.loop_count}/{MAX_LOOPS})...")
                if st.button("🛑 DỪNG NGAY"):
                    st.session_state.is_auto_running = False
                    st.success("Đã dừng thủ công.")
                    st.rerun()

            st.divider()
            res = st.session_state.analysis_result
            
            # Render Mermaid nếu có
            if "```mermaid" in res:
                try:
                    m_code = res.split("```mermaid")[1].split("```")[0]
                    st_mermaid(m_code, height=500)
                except: pass
            
            # Hiển thị Text trong Expander
            with st.expander("📄 Nội dung chi tiết", expanded=True):
                st.markdown(res)

            # Nút tải Word
            doc = create_docx(res)
            doc_io = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(doc_io.name)
            with open(doc_io.name, "rb") as f:
                st.download_button("📥 Tải Báo Cáo (.docx)", f, "Bao_Cao_AI_Studio.docx", type="primary")
            os.remove(doc_io.name)

            # LOGIC AUTO-CONTINUE (LOOP)
            if st.session_state.is_auto_running and main_mode.startswith("📝"):
                # 1. Kiểm tra điều kiện dừng (Lỗi hoặc Max Loops)
                if "[DỪNG:" in res or "[CẢNH BÁO:" in res:
                    st.session_state.is_auto_running = False
                    st.error("⚠️ Dừng do vấn đề bản quyền/an toàn.")
                elif st.session_state.loop_count >= MAX_LOOPS:
                    st.session_state.is_auto_running = False
                    st.warning(f"🛑 Đã đạt giới hạn {MAX_LOOPS} vòng lặp. Dừng để bảo vệ Quota.")
                else:
                    # 2. Chờ 2s để UI cập nhật
                    time.sleep(2)
                    
                    with st.spinner("Đang nghe tiếp đoạn sau..."):
                        try:
                            # 3. Lấy mỏ neo thông minh
                            last_part = get_smart_anchor(res)
                            
                            c_prompt = f"""
                            CONTEXT: Đang gỡ băng dở dang.
                            MỎ NEO (Đoạn cuối đã chép): "...{last_part}"
                            NHIỆM VỤ: Tìm vị trí mỏ neo trong file, chép tiếp NGUYÊN VĂN đoạn ngay sau đó. 
                            TUYỆT ĐỐI KHÔNG viết lại đoạn mỏ neo.
                            """
                            
                            model = genai.GenerativeModel(model_version)
                            # Sử dụng config cũ
                            c_res = model.generate_content(
                                [c_prompt] + st.session_state.gemini_files, 
                                generation_config=genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.2),
                                safety_settings=[{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}] # Rút gọn
                            )
                            
                            safe_c_text = get_safe_response(c_res)

                            # 4. Kiểm tra kết quả nối
                            if len(safe_c_text) < 50 or "kết thúc" in safe_c_text.lower() or "[DỪNG:" in safe_c_text:
                                st.session_state.is_auto_running = False
                                st.success("✅ Đã hoàn tất (hoặc không còn nội dung)!")
                                if len(safe_c_text) > 5:
                                    st.session_state.analysis_result += "\n\n" + safe_c_text
                                    st.rerun()
                            else:
                                st.session_state.analysis_result += "\n\n" + safe_c_text
                                st.session_state.loop_count += 1
                                st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi vòng lặp: {e}")
                            st.session_state.is_auto_running = False

    with tab_chat:
        st.header("💬 Chat với dữ liệu")
        if st.session_state.gemini_files:
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"]): st.markdown(m["content"])
            if inp := st.chat_input("Hỏi AI về nội dung file..."):
                st.session_state.chat_history.append({"role": "user", "content": inp})
                with st.chat_message("user"): st.markdown(inp)
                with st.chat_message("assistant"):
                    try:
                        m = genai.GenerativeModel(model_version)
                        r = m.generate_content(
                            st.session_state.gemini_files + [f"Trả lời dựa trên file: {inp}"]
                        )
                        st.markdown(r.text); st.session_state.chat_history.append({"role": "assistant", "content": r.text})
                    except: st.error("Lỗi chat.")
        else: st.info("👈 Vui lòng Upload file ở tab bên cạnh trước.")

if __name__ == "__main__":
    main()
