# know

このリポジトリは、複数形式のドキュメントを一元管理するマルチモーダルRAGシステムのサンプル実装です。

## ディレクトリ構成
- `know-unified-rag/` - Streamlit アプリとコアモジュール
- `knowledge_gpt_app/` - 既存のナレッジ検索ツール（参考実装）
- `mm_kb_builder/` - 画像やCADデータ取り込み用のユーティリティ

## 使用方法
1. 依存ライブラリをインストールします。
   ```bash
   pip install -r know-unified-rag/requirements.txt
   ```
2. 環境変数 `OPENAI_API_KEY` を設定したうえで Streamlit アプリを起動します。
   ```bash
   streamlit run know-unified-rag/app.py
   ```

アップロードしたファイルは自動的に解析され、ベクトルストアへ登録されます。チャット欄から質問を入力すると、登録済みドキュメントを参照した回答が得られます。
