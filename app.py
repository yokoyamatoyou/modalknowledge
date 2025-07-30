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
                    vector_store.delete_document(doc_id)
                    st.rerun()

            with st.expander("詳細を表示"):
                # st.json(chunks) # Display all chunks and metadata
                for chunk in chunks:
                    st.write(f"**チャンク:** {chunk['text']}")
                    # メタデータを日本語で表示
                    meta_display = {
                        "ソースファイル": chunk['metadata'].get('ソースファイル', '不明'),
                        "ページ番号": chunk['metadata'].get('ページ番号', 'N/A'),
                        "種類": chunk['metadata'].get('種類', 'N/A'),
                        "作成者": chunk['metadata'].get('author', '未設定'),
                        "有効期限": chunk['metadata'].get('expiration_date', '未設定'),
                        "AI要約": chunk['metadata'].get('ai_summary', 'なし'),
                        "AIタグ": chunk['metadata'].get('ai_tags', [])
                    }
                    st.json(meta_display)

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
                    # ... (GUI from previous step) ...
                    st.session_state.metadata_map[file_id]['author'] = st.text_input("作成者", value=st.session_state.metadata_map[file_id]['author'], key=f"author_{file_id}")
                    st.session_state.metadata_map[file_id]['expiration_date'] = st.date_input("有効期限", value=st.session_state.metadata_map[file_id]['expiration_date'], key=f"exp_date_{file_id}")
                    st.subheader("カスタムメタデータ")
                    st.caption("例：項目名「プロジェクト名」、内容「次世代RAG開発」")
                    # ... (rest of the custom metadata UI) ...

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
                        # Convert date object to string before processing
                        meta_for_processing = session_meta.copy()
                        if isinstance(meta_for_processing.get('expiration_date'), date):
                            meta_for_processing['expiration_date'] = meta_for_processing['expiration_date'].strftime("%Y-%m-%d")
                        
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

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_input := st.chat_input("質問を入力してください"):
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.spinner("考え中..."):
                result = rag_engine.answer_question(user_input)
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