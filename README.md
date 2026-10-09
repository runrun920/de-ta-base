1. 【データ元】 fe_study_master_23sheets（CSVを読み込んでDBを作るプログラムを実行）
2. 【データベース】 fe_study.db（DBからデータを引っ張ってきて画面に表示）
3. 【アプリ画面】 app.py（Streamlit）

# 基本情報技術者試験（FE）学習・実験システム

基本情報技術者試験（科目A）の用語学習および理解度向上を目的としたWebアプリケーション・データベースシステム
「直感的な例え話」「身近な実用例」「初級者向け解説」「上級者向け解説」および「科目A形式の4択予想問題」を備えている

## このリポジトリの目的

1. **`fe_study_master.csv`**（「例え話」「実用例」「科目A予想問題」「文系学生向け解説」「情報科学生向け解説」が入ったCSV）を用意する
2. そのCSVから **データベース（`fe_study.db`）** を作る
3. そのデータベースを読み込んで **`app.py`（Streamlitアプリ）** で画面に表示する

---

## 実行手順

### 1. 準備：リポジトリのクローン（初回のみ）
git clone [https://github.com/runrun920/de-ta-base.git](https://github.com/runrun920/de-ta-base.git)
cd de-ta-base

### 2. 必要なものを入れる
pip3 install pandas streamlit
pip3 install pandas streamlit openpyxl google-genai

### 3. データ生成・メンテナンス用スクリプト（管理者向け）
fe_study_master_23sheets.xlsx を読み込み、Google Gemini API を用いて未作成の用語に対する
「直感的例え話」「身近な実用例」「科目A予想問題」「初級者向け解説」「上級者向け解説」を自動生成し、Excelに保存

python3 generate_and_save_to_excel.py

### 4. データベースを作る
Excelファイル（fe_study_master_23sheets.xlsx）の内容をSQLiteデータベース（fe_study.db）に反映する
python3 sync_db.py

### 5. アプリを起動
1. streamlit run app.py
2. streamlit run admin_app.py --server.port 8502
（※adminは管理者用画面。学習者の学習状況を見られる画面）
