import os
import shutil
from pathlib import Path
from datetime import date
import streamlit as st
from openai import OpenAI
from src import main_processor
from src.vector_store import VectorStoreManager
from src.rag_engine import RAGEngine

# --- 初期化 ---
@st.cache_resource
def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        st.error("環境変数にOPENAI_API_KEYが設定されていません。")
        st.stop()
    return OpenAI(api_key=api_key)

@st.cache_resource
def get_vector_store(_client: OpenAI) -> VectorStoreManager:
    return VectorStoreManager(_client)

@st.cache_resource
def get_rag_engine(_vector_store: VectorStoreManager, _client: OpenAI) -> RAGEngine:
    return RAGEngine(_vector_store, _client)

TEMP_DIR = Path("uploaded_temp")

# --- UI関数 ---
def display_knowledge_base(vector_store: VectorStoreManager):
    st.header("登録済みナレッジ")

    if 'pending_delete' not in st.session_state:
        st.session_state.pending_delete = None

    if not vector_store.documents:
        st.info("現在、登録されているナレッジはありません。")
        return

    for doc_id, chunks in vector_store.documents.items():
        if not chunks:
            continue
        
        source_file = chunks[0]["metadata"].get("source_file", "不明なファイル")
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.subheader(source_file)
                # Display thumbnail if available
                doc_dir = vector_store.docs_path / doc_id
                thumb_files = list(doc_dir.glob("thumbnail_*.png"))
                if thumb_files:
                    with open(thumb_files[0], "rb") as f:
                        st.image(f.read(), width=100)
            with col2:
                if st.button("削除", key=f"delete_{doc_id}", type="primary"):
                    st.session_state.pending_delete = doc_id
                    st.rerun()

            with st.expander("詳細を表示"):
                # st.json(chunks) # Display all chunks and metadata
                for chunk in chunks:
                    st.write(f"**チャンク:** {chunk['text']}")
                    # メタデータを日本語で表示
                    meta_display = {
                        "ソースファイル": chunk['metadata'].get('source_file', '不明'),
                        "ページ番号": chunk['metadata'].get('page', 'N/A'),
                        "種類": chunk['metadata'].get('type', 'N/A'),
                        "作成者": chunk['metadata'].get('author', '未設定'),
                        "有効期限": chunk['metadata'].get('expiration_date', '未設定'),
                        "AI要約": chunk['metadata'].get('ai_summary', 'なし'),
                        "AIタグ": chunk['metadata'].get('ai_tags', [])
                    }
                    st.json(meta_display)

    # --- 削除確認モーダル ---
    if st.session_state.pending_delete:
        doc_id = st.session_state.pending_delete
        st.warning("ナレッジを削除しますか？")
        pw = st.text_input("削除パスワード", type="password", key="delete_pw")
        col_del, col_cancel = st.columns(2)
        if col_del.button("はい", key="confirm_yes"):
            required = os.environ.get("DELETE_PASSWORD")
            if required and pw != required:
                st.error("パスワードが一致しません")
            else:
                vector_store.delete_document(doc_id)
                st.session_state.pending_delete = None
                st.success("削除が完了しました")
                st.rerun()
        if col_cancel.button("いいえ", key="confirm_no"):
            st.session_state.pending_delete = None
            st.rerun()

# --- メイン処理 ---
def main() -> None:
    st.set_page_config(layout="wide", page_title="統合ナレッジ検索システム")
    st.title("統合ナレッジ検索システム")

    client = get_openai_client()
    vector_store = get_vector_store(client)
    rag_engine = get_rag_engine(vector_store, client)

    # --- ナレッジ登録 ---
    with st.sidebar:
        st.header("ナレッジ登録")
        if 'metadata_map' not in st.session_state:
            st.session_state.metadata_map = {}

        uploaded_files = st.file_uploader(
            "ファイルを選択",
            accept_multiple_files=True,
            type=['txt', 'pdf', 'docx', 'png', 'jpg', 'jpeg']
        )

        if uploaded_files:
            for file in uploaded_files:
                file_id = file.file_id
                if file_id not in st.session_state.metadata_map:
                    st.session_state.metadata_map[file_id] = {
                        "author": "", "expiration_date": date.today(), "custom_metadata": []
                    }
                with st.expander(f"ファイル: {file.name}"):
                    st.session_state.metadata_map[file_id]['author'] = st.text_input(
                        "作成者",
                        value=st.session_state.metadata_map[file_id]['author'],
                        key=f"author_{file_id}"
                    )
                    st.session_state.metadata_map[file_id]['expiration_date'] = st.date_input(
                        "有効期限",
                        value=st.session_state.metadata_map[file_id]['expiration_date'],
                        key=f"exp_date_{file_id}"
                    )
                    st.subheader("カスタムメタデータ")
                    st.caption("例：項目名『プロジェクト名』、内容『次世代RAG開発』")
                    custom_list = st.session_state.metadata_map[file_id]['custom_metadata']
                    remove_indices = []
                    for idx, item in enumerate(custom_list):
                        col_k, col_v, col_d = st.columns([3, 3, 1])
                        col_k.text_input("キー", value=item['key'], key=f"disp_key_{file_id}_{idx}", disabled=True)
                        col_v.text_input("値", value=item['value'], key=f"disp_val_{file_id}_{idx}", disabled=True)
                        if col_d.button("削除", key=f"del_meta_{file_id}_{idx}"):
                            remove_indices.append(idx)
                    for idx in sorted(remove_indices, reverse=True):
                        custom_list.pop(idx)
                    new_key = st.text_input("キー", key=f"new_key_{file_id}")
                    new_val = st.text_input("値", key=f"new_val_{file_id}")
                    if st.button("追加", key=f"add_meta_{file_id}"):
                        if new_key:
                            custom_list.append({"key": new_key, "value": new_val})
                            st.session_state[f"new_key_{file_id}"] = ""
                            st.session_state[f"new_val_{file_id}"] = ""
                            st.rerun()

        if st.button("選択したファイルをナレッジに登録"):
            if uploaded_files:
                TEMP_DIR.mkdir(exist_ok=True)
                with st.spinner("登録処理中..."):
                    for file in uploaded_files:
                        # Save to a temporary location
                        temp_path = TEMP_DIR / file.name
                        with open(temp_path, "wb") as f:
                            f.write(file.getbuffer())

                        # Process and add to vector store
                        session_meta = st.session_state.metadata_map.get(file.file_id, {})
                        meta_for_processing = {
                            "author": session_meta.get("author", ""),
                            "expiration_date": session_meta.get("expiration_date"),
                        }
                        if isinstance(meta_for_processing.get('expiration_date'), date):
                            meta_for_processing['expiration_date'] = meta_for_processing['expiration_date'].strftime("%Y-%m-%d")
                        for item in session_meta.get('custom_metadata', []):
                            meta_for_processing[item.get('key')] = item.get('value')
                        
                        chunks, thumb_path = main_processor.process_file(str(temp_path), meta_for_processing, client, TEMP_DIR)
                        if chunks:
                            vector_store.add_document(temp_path, chunks, thumb_path)

                shutil.rmtree(TEMP_DIR) # Clean up temp directory
                st.session_state.metadata_map.clear()
                st.success("ナレッジの登録が完了しました！")
                st.rerun()
            else:
                st.warning("ファイルをアップロードしてください。")

    # --- ナレッジ一覧とチャット ---
    tab1, tab2 = st.tabs(["チャット", "ナレッジ管理"]) 

    with tab1:
        st.header("チャット")
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "filter_author" not in st.session_state:
            st.session_state.filter_author = ""
        if "filter_tags" not in st.session_state:
            st.session_state.filter_tags = []
        if "filter_keyword" not in st.session_state:
            st.session_state.filter_keyword = ""
        if "use_date_filter" not in st.session_state:
            st.session_state.use_date_filter = False
        if "filter_start_date" not in st.session_state:
            st.session_state.filter_start_date = date.today()
        if "filter_end_date" not in st.session_state:
            st.session_state.filter_end_date = date.today()

        with st.expander("検索オプション"):
            st.text_input("作成者で絞り込み", key="filter_author")
            tag_str = st.text_input("タグで絞り込み(カンマ区切り)", key="filter_tag")
            st.session_state.filter_tags = [t.strip() for t in tag_str.split(",") if t.strip()]
            st.text_input("キーワード", key="filter_keyword")
            st.checkbox("有効期限で範囲指定", key="use_date_filter")
            if st.session_state.use_date_filter:
                col_s, col_e = st.columns(2)
                col_s.date_input("開始日", key="filter_start_date")
                col_e.date_input("終了日", key="filter_end_date")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_input := st.chat_input("質問を入力してください"):
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.spinner("考え中..."):
                filters = {}

                # **修正**: フィルタの適用を明確化
                if st.session_state.filter_author:
                    filters["author"] = st.session_state.filter_author
                if st.session_state.filter_tags:
                    filters["tag"] = st.session_state.filter_tags
                if st.session_state.filter_keyword:
                    filters["keyword"] = st.session_state.filter_keyword

                # **重要**: ユーザーが明示的に日付範囲を指定した場合のみ適用
                # そうでなければRAGエンジンで自動的に期限切れフィルタが適用される
                if st.session_state.use_date_filter:
                    start = st.session_state.filter_start_date.strftime("%Y-%m-%d")
                    end = st.session_state.filter_end_date.strftime("%Y-%m-%d")
                    filters["expiration_date_start"] = start
                    filters["expiration_date_end"] = end
                    # 明示的な日付範囲が指定された場合は、自動の期限切れフィルタを無効化
                    print(f"[DEBUG] ユーザー指定の日付範囲: {start} から {end}")
                else:
                    print("[DEBUG] 日付フィルタ未指定 - RAGエンジンで自動期限切れフィルタが適用されます")

                # **デバッグ情報の表示**
                if filters:
                    st.info(f"適用フィルタ: {filters}")

                result = rag_engine.answer_question(user_input, filters)
                answer = result.get("answer", "申し訳ありません、回答を生成できませんでした。")
                sources = result.get("sources", [])
                
                response_content = answer
                if sources:
                    response_content += "\n\n**参照ソース:**\n"
                    for source in sources:
                        metadata = source.get("metadata", {})
                        source_file = metadata.get("source_file", "不明")
                        doc_id = source.get("doc_id")
                        
                        # Display thumbnail if available
                        if doc_id:
                            doc_dir = vector_store.docs_path / doc_id
                            thumb_files = list(doc_dir.glob("thumbnail_*.png"))
                            if thumb_files:
                                st.image(str(thumb_files[0]), width=100)
                        
                        response_content += f"- {source_file} (Page: {metadata.get('page', 'N/A')})\n"

            with st.chat_message("assistant"):
                st.markdown(response_content)

            st.session_state.messages.append({"role": "assistant", "content": response_content})

    with tab2:
        display_knowledge_base(vector_store)

if __name__ == "__main__":
    main()

