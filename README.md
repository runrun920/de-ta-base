1. 【データ元】 fe_study_master.csv（CSVを読み込んでDBを作るプログラムを実行）
2. 【データベース】 fe_study.db（DBからデータを引っ張ってきて画面に表示）
3. 【アプリ画面】 app.py（Streamlit）

# 基本情報技術者試験 学習支援システム

## このリポジトリの目的
来住先生からの指示に基づき、以下の流れで動くシステムを作る。

1. **`fe_study_master.csv`**（「例え話」「実用例」「科目A予想問題」「文系学生向け解説」「情報科学生向け解説」が入ったCSV）を用意する
2. そのCSVから **データベース（`fe_study.db`）** を作る
3. そのデータベースを読み込んで **`app.py`（Streamlitアプリ）** で画面に表示する

---

## 実行手順

### 1. 準備（初回のみ）
git clone https://github.com/runrun920/de-ta-base.git
cd de-ta-base

### 2. 必要なものを入れる
pip3 install pandas streamlit

### 3. データベースを作る
python3 make_db.py

### 3. アプリを起動
streamlit run app.py
