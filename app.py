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
# Biến kiểm soát trạng thá
