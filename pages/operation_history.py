import json
from pathlib import Path
import streamlit as st

from src.utils import LOG_FILE

st.set_page_config(page_title="操作履歴", layout="wide")
st.title("操作履歴")

if LOG_FILE.exists():
    logs = [json.loads(line) for line in LOG_FILE.read_text(encoding="utf-8").splitlines()]
    if logs:
        st.table(logs)
    else:
        st.info("ログがまだありません。")
else:
    st.info("ログファイルが存在しません。")
