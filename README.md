# know

このリポジトリは、複数形式のドキュメントを一元管理するマルチモーダルRAGシステムのサンプル実装です。

## ディレクトリ構成
- `app.py` - Streamlit アプリ本体
- `pages/` - 追加のUIページ
  - `operation_history.py` - 操作履歴の表示
- `src/` - コアモジュール
  - `parsers/` - ファイル解析ロジック
  - `main_processor.py` - アップロード処理のエントリ
  - `vector_store.py` - ベクトルストア管理
  - `rag_engine.py` - RAG エンジン
  - `utils.py` - 補助関数

## 使用方法
1. 依存ライブラリをインストールします。
   ```bash
   pip install -r requirements.txt
   ```
2. 環境変数 `OPENAI_API_KEY` を設定したうえで Streamlit アプリを起動します。
   ```bash
   streamlit run app.py
   ```

アップロードしたファイルは自動的に解析され、ベクトルストアへ登録されます。チャット欄から質問を入力すると、登録済みドキュメントを参照した回答が得られます。
