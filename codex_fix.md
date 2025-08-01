# 🔧 Codex向け詳細修正指示書: ナレッジ検索問題の解決

## 📋 **修正の概要**
現在、ナレッジを登録しても「ナレッジが見つかりません」と表示される問題があります。この問題を3つのフェーズに分けて修正します。

**問題の原因**: RAGエンジンで期限切れフィルタが正しく実装されていないため、すべてのナレッジが除外されています。

---

## 🚀 **事前準備**

### ステップ0-1: 作業ブランチの作成
```bash
# 現在のブランチを確認
git branch

# developブランチに移動（なければmainから作成）
git checkout develop
# または git checkout -b develop

# 修正用の新しいブランチを作成
git checkout -b fix/search-issue
```

### ステップ0-2: 現在の問題を確認
1. アプリを起動: `streamlit run app.py`
2. ファイルを1つアップロードして登録
3. チャットで質問して「ナレッジが見つかりません」が表示されることを確認
4. アプリを停止: `Ctrl+C`

---

## 🔄 **フェーズ1: RAGエンジンの修正**

### ステップ1-1: バックアップ作成
```bash
# バックアップを作成
cp src/rag_engine.py src/rag_engine.py.backup
```

### ステップ1-2: rag_engine.pyを開く
`src/rag_engine.py` ファイルを開いてください。

### ステップ1-3: answer_questionメソッドを修正

**現在のコード（19行目付近）:**
```python
def answer_question(self, question: str, filters: Dict[str, object] | None = None) -> Dict[str, object]:
    """Answer a question using current knowledge base."""
    search_filters = filters or {}
    docs = self.vector_store.search(question, filters=search_filters)
```

**修正後のコード:**
```python
def answer_question(self, question: str, filters: Dict[str, object] | None = None) -> Dict[str, object]:
    """Answer a question using current knowledge base."""
    search_filters = filters or {}
    
    # **重要な修正**: 期限切れフィルタを自動適用（設計書通り）
    # ただし、ユーザーが明示的に日付範囲を指定している場合は除く
    if "expiration_date_start" not in search_filters and "expiration_date_end" not in search_filters:
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        search_filters["expiration_date_gt"] = today
        print(f"[DEBUG] 期限切れフィルタ適用: {today} より後の有効期限のみ検索")
    
    docs = self.vector_store.search(question, filters=search_filters)
    
    # **デバッグログを追加**
    print(f"[DEBUG] 検索クエリ: {question}")
    print(f"[DEBUG] 適用フィルタ: {search_filters}")
    print(f"[DEBUG] 検索結果数: {len(docs)}")
```

### ステップ1-4: importを追加
ファイルの上部（2行目付近）に、以下のimportを追加してください：

**現在のimport部分:**
```python
from __future__ import annotations

from typing import List, Dict

import openai
```

**修正後のimport部分:**
```python
from __future__ import annotations

from datetime import date
from typing import List, Dict

import openai
```

### ステップ1-5: エラーメッセージを変更
29行目付近の以下のコードを修正してください：

**現在のコード:**
```python
if not docs:
    return {"answer": "ナレッジベースに情報がありません", "sources": []}
```

**修正後のコード:**
```python
if not docs:
    return {"answer": "ナレッジベースに情報がありません。登録済みナレッジの有効期限を確認してください。", "sources": []}
```

### ステップ1-6: APIエラーハンドリングを改善
40行目付近の以下のコードを修正してください：

**現在のコード:**
```python
except openai.OpenAIError:
    answer = "回答生成中にエラーが発生しました"
```

**修正後のコード:**
```python
except openai.OpenAIError as e:
    print(f"[DEBUG] OpenAI API エラー: {e}")
    answer = "回答生成中にエラーが発生しました"
```

### ステップ1-7: 修正内容を保存して自己テスト
1. ファイルを保存
2. ターミナルで構文チェック: `python -m py_compile src/rag_engine.py`
3. エラーが出た場合は、コードを再確認して修正
4. エラーが出なければ次のステップへ

---

## 🔄 **フェーズ2: ベクトルストアの修正**

### ステップ2-1: バックアップ作成
```bash
cp src/vector_store.py src/vector_store.py.backup
```

### ステップ2-2: vector_store.pyを開く
`src/vector_store.py` ファイルを開いてください。

### ステップ2-3: _match_filtersメソッドを見つける
約75行目付近の `def _match_filters(self, chunk: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:` メソッドを見つけてください。

### ステップ2-4: メソッド全体を置き換え

**現在のメソッド全体を削除して、以下のコードに置き換えてください:**

```python
def _match_filters(self, chunk: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """Return True if the chunk satisfies the filter conditions."""
    if not filters:
        return True

    meta = chunk.get("metadata", {})
    text = chunk.get("text", "")
    
    # **デバッグログを追加**
    print(f"[DEBUG] チャンクのメタデータ: {meta}")
    print(f"[DEBUG] 適用中のフィルタ: {filters}")
    
    for key, value in filters.items():
        if key == "expiration_date_gt":
            exp = meta.get("expiration_date")
            print(f"[DEBUG] 有効期限チェック: {exp} > {value}")
            if not exp:
                # 有効期限が設定されていない場合は除外
                print(f"[DEBUG] 有効期限未設定のため除外")
                return False
            # 文字列での日付比較（YYYY-MM-DD形式を前提）
            if exp <= value:
                print(f"[DEBUG] 期限切れのため除外: {exp} <= {value}")
                return False
        elif key == "expiration_date_start":
            exp = meta.get("expiration_date")
            print(f"[DEBUG] 開始日チェック: {exp} >= {value}")
            if exp and exp < value:
                return False
        elif key == "expiration_date_end":
            exp = meta.get("expiration_date")
            print(f"[DEBUG] 終了日チェック: {exp} <= {value}")
            if exp and exp > value:
                return False
        elif key == "author":
            if meta.get("author") != value:
                print(f"[DEBUG] 作成者不一致: {meta.get('author')} != {value}")
                return False
        elif key == "tag":
            tags = meta.get("ai_tags", [])
            if isinstance(value, str):
                if value not in tags:
                    print(f"[DEBUG] タグ不一致: {value} not in {tags}")
                    return False
            else:
                if not any(v in tags for v in value):
                    print(f"[DEBUG] タグ不一致: {value} not in {tags}")
                    return False
        elif key == "keyword":
            if value.lower() not in text.lower():
                print(f"[DEBUG] キーワード不一致: {value} not in text")
                return False
        else:
            if meta.get(key) != value:
                print(f"[DEBUG] メタデータ不一致: {meta.get(key)} != {value}")
                return False
    
    print(f"[DEBUG] フィルタ条件をすべて満たしています")
    return True
```

### ステップ2-5: 修正内容を保存して自己テスト
1. ファイルを保存
2. ターミナルで構文チェック: `python -m py_compile src/vector_store.py`
3. エラーが出た場合は、コードを再確認して修正
4. エラーが出なければ次のステップへ

---

## 🔄 **フェーズ3: アプリのチャット部分修正**

### ステップ3-1: バックアップ作成
```bash
cp app.py app.py.backup
```

### ステップ3-2: app.pyを開く
`app.py` ファイルを開いてください。

### ステップ3-3: チャット入力処理部分を見つける
約120行目付近の `if user_input := st.chat_input("質問を入力してください"):` の部分を見つけてください。

### ステップ3-4: フィルタ処理部分を修正

**以下の部分を見つけてください（約130行目付近）:**
```python
with st.spinner("考え中..."):
    filters = {}
    if st.session_state.filter_author:
        filters["author"] = st.session_state.filter_author
    if st.session_state.filter_tags:
        filters["tag"] = st.session_state.filter_tags
    if st.session_state.filter_keyword:
        filters["keyword"] = st.session_state.filter_keyword
    if st.session_state.use_date_filter:
        start = st.session_state.filter_start_date.strftime("%Y-%m-%d")
        end = st.session_state.filter_end_date.strftime("%Y-%m-%d")
        filters["expiration_date_start"] = start
        filters["expiration_date_end"] = end
    result = rag_engine.answer_question(user_input, filters)
```

**上記のコードを以下に置き換えてください:**
```python
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
```

### ステップ3-5: 修正内容を保存して自己テスト
1. ファイルを保存
2. ターミナルで構文チェック: `python -m py_compile app.py`
3. エラーが出た場合は、コードを再確認して修正
4. エラーが出なければ次のステップへ

---

## 🧪 **フェーズ4: 統合テスト**

### ステップ4-1: アプリを起動してテスト
```bash
streamlit run app.py
```

### ステップ4-2: 動作確認
1. **ナレッジ登録テスト**:
   - テキストファイルまたは画像を1つアップロード
   - 作成者名を入力
   - **重要**: 有効期限を**明日以降の日付**に設定
   - 登録ボタンをクリック
   - 「登録が完了しました！」が表示されることを確認

2. **検索テスト**:
   - チャットで関連する質問を入力
   - コンソール（ターミナル）にデバッグログが出力されることを確認
   - 「ナレッジが見つかりません」ではなく、適切な回答が返ることを確認

### ステップ4-3: デバッグログの確認
ターミナルに以下のようなログが出力されることを確認してください：
```
[DEBUG] 期限切れフィルタ適用: 2025-07-31 より後の有効期限のみ検索
[DEBUG] 検索クエリ: テストの質問
[DEBUG] 適用フィルタ: {'expiration_date_gt': '2025-07-31'}
[DEBUG] 検索結果数: 1
```

### ステップ4-4: エラーが発生した場合
1. **「期限切れのため除外」が表示される場合**:
   - ナレッジの有効期限を明日以降に設定し直してください
   
2. **「検索結果数: 0」が表示される場合**:
   - FAISSインデックスが正しく保存されていない可能性があります
   - `data/` フォルダを削除して、ナレッジを再登録してください

3. **構文エラーが発生する場合**:
   - バックアップファイルから復元して、修正を再実行してください

---

## 🎯 **フェーズ5: コミットとプルリクエスト**

### ステップ5-1: 変更をコミット
```bash
# 変更されたファイルを確認
git status

# すべての変更をステージング
git add src/rag_engine.py src/vector_store.py app.py

# コミット（メッセージは具体的に）
git commit -m "fix: RAGエンジンの期限切れフィルタ実装とデバッグログ追加

- RAGエンジンで自動的に期限切れナレッジを除外するフィルタを実装
- ベクトルストアのフィルタ処理にデバッグログを追加  
- アプリのフィルタ適用ロジックを明確化
- ナレッジ検索で「見つかりません」が表示される問題を修正"
```

### ステップ5-2: リモートにプッシュ
```bash
git push origin fix/search-issue
```

### ステップ5-3: プルリクエスト作成
1. GitHubのリポジトリページに移動
2. 「Compare & pull request」ボタンをクリック
3. タイトル: `fix: ナレッジ検索問題の修正`
4. 説明に以下を記載:
```markdown
## 修正内容
- RAGエンジンで期限切れナレッジを自動除外する機能を実装
- ベクトルストアの検索フィルタ処理を改善
- デバッグログを追加して問題の特定を容易に

## テスト結果
- [x] ナレッジの登録が正常に動作する
- [x] 有効期限内のナレッジが検索できる
- [x] 期限切れのナレッジが除外される
- [x] デバッグログが正しく出力される

## 修正ファイル
- src/rag_engine.py
- src/vector_store.py  
- app.py
```

### ステップ5-4: プルリクエストの確認
1. 「Create pull request」をクリック
2. エラーが発生した場合は、ファイルの競合を解決
3. マージが可能になったら「Merge pull request」をクリック

---

## ⚠️ **トラブルシューティング**

### よくあるエラーと対処法

1. **インポートエラー**:
   ```
   ModuleNotFoundError: No module named 'datetime'
   ```
   → `from datetime import date` が正しく追加されているか確認

2. **構文エラー**:
   ```
   SyntaxError: invalid syntax
   ```
   → インデント（スペース4つ）が正しいか確認
   → 括弧の閉じ忘れがないか確認

3. **マージコンフリクト**:
   ```
   CONFLICT (content): Merge conflict in app.py
   ```
   → バックアップファイルから復元して修正を再実行

4. **FAISSエラー**:
   ```
   RuntimeError: Error in faiss
   ```
   → `data/` フォルダを削除してナレッジを再登録

---

## ✅ **修正完了の確認リスト**

- [x] フェーズ1: RAGエンジンの修正完了
- [x] フェーズ2: ベクトルストアの修正完了
- [x] フェーズ3: アプリの修正完了
- [x] フェーズ4: 統合テストでナレッジが検索できることを確認
- [x] フェーズ5: GitHubにプルリクエストを作成してマージ

すべてのチェックボックスが完了したら、修正は成功です！
