import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(page_title="FE-AI Tutor 管理者ダッシュボード", layout="wide", page_icon="📊")

st.markdown("""
<meta name="google" content="notranslate">
<style>
    html, body, [class*="css"], .stApp {
        translate: no !important;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "fe_study.db"

if not os.path.exists(DB_FILE):
    st.error("⚠️ データベース（fe_study.db）が見つかりません。先に `python3 build_db.py` を実行してください。")
    st.stop()

def get_conn():
    return sqlite3.connect(DB_FILE)

conn = get_conn()

st.title("📊 学習行動・研究データ分析ダッシュボード")
st.caption("正規化データベース（fe_study.db）の各分離テーブルおよび学習ログを確認できます。")

col1, col2, col3, col4, col5 = st.columns(5)

try:
    all_terms_cnt = pd.read_sql("SELECT COUNT(*) FROM terms", conn).iloc[0, 0]
except Exception:
    all_terms_cnt = 0

try:
    meta_cnt = pd.read_sql("SELECT COUNT(*) FROM term_metaphors", conn).iloc[0, 0]
except Exception:
    meta_cnt = 0

try:
    ex_cnt = pd.read_sql("SELECT COUNT(*) FROM term_examples", conn).iloc[0, 0]
except Exception:
    ex_cnt = 0

try:
    q_cnt = pd.read_sql("SELECT COUNT(*) FROM questions", conn).iloc[0, 0]
except Exception:
    q_cnt = 0

try:
    log_cnt = pd.read_sql("SELECT COUNT(*) FROM quiz_logs", conn).iloc[0, 0]
except Exception:
    log_cnt = 0

col1.metric("用語マスター", f"{all_terms_cnt} 語")
col2.metric("例え話", f"{meta_cnt} 件")
col3.metric("実用例", f"{ex_cnt} 件")
col4.metric("演習問題", f"{q_cnt} 問")
col5.metric("総解答ログ数", f"{log_cnt} 回")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "🗄️ データベース全テーブル閲覧",
    "👤 学生別 学習進捗・正答率", 
    "⚖️ 問題バランス・正解分布検証", 
    "📈 学習行動シーケンス・ログ出力"
])

with tab1:
    st.subheader("データベース（fe_study.db）のテーブル・ビュー一覧")
    
    table_choice = st.selectbox(
        "確認したいテーブルを選択してください：",
        [
            "terms_master (VIEW: 全テーブル結合の統合表示)",
            "terms (TABLE: 用語・公式定義)",
            "term_metaphors (TABLE: 比喩・例え話)",
            "term_examples (TABLE: 身近な実用例)",
            "questions (TABLE: 4択問題マスター)",
            "question_explanations_beginner (TABLE: 文系・初学者向け解説)",
            "question_explanations_advanced (TABLE: 情報科学科向け解説)",
            "term_categories (TABLE: シラバス23分類)",
            "users (TABLE: 学生アカウント)",
            "quiz_logs (TABLE: 問題解答ログ)",
            "term_logs (TABLE: 用語閲覧ログ)"
        ]
    )
    
    if table_choice.startswith("terms_master"):
        df = pd.read_sql("SELECT * FROM terms_master", conn)
        st.success(f"▼ terms_master (VIEW) 表示件数：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("terms ("):
        df = pd.read_sql("SELECT * FROM terms", conn)
        st.write(f"▼ terms テーブル：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("term_metaphors"):
        df = pd.read_sql("""
        SELECT m.id, t.term_name AS 用語名, m.metaphor_text AS 例え話, m.source_ai AS 作成元
        FROM term_metaphors m
        JOIN terms t ON m.term_id = t.id
        """, conn)
        st.success(f"▼ term_metaphors（例え話テーブル）：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("term_examples"):
        df = pd.read_sql("""
        SELECT e.id, t.term_name AS 用語名, e.example_text AS 身近な実用例, e.source_ai AS 作成元
        FROM term_examples e
        JOIN terms t ON e.term_id = t.id
        """, conn)
        st.success(f"▼ term_examples（実用例テーブル）：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("questions"):
        df = pd.read_sql("""
        SELECT q.id, t.term_name AS 用語名, q.question_text AS 問題文, q.choice_a, q.choice_b, q.choice_c, q.choice_d, q.correct_ans AS 正解
        FROM questions q
        JOIN terms t ON q.term_id = t.id
        """, conn)
        st.write(f"▼ questions テーブル：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("question_explanations_beginner"):
        df = pd.read_sql("""
        SELECT qeb.id, qeb.question_id, q.question_text AS 対象問題, qeb.explanation AS 文系初学者向け解説
        FROM question_explanations_beginner qeb
        JOIN questions q ON qeb.question_id = q.id
        """, conn)
        st.success(f"▼ question_explanations_beginner（文系解説テーブル）：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("question_explanations_advanced"):
        df = pd.read_sql("""
        SELECT qea.id, qea.question_id, q.question_text AS 対象問題, qea.explanation AS 情報科学科向け解説
        FROM question_explanations_advanced qea
        JOIN questions q ON qea.question_id = q.id
        """, conn)
        st.success(f"▼ question_explanations_advanced（情報系解説テーブル）：{len(df)} 件")
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("term_categories"):
        df = pd.read_sql("SELECT * FROM term_categories", conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("users"):
        df = pd.read_sql("SELECT * FROM users", conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("quiz_logs"):
        df = pd.read_sql("SELECT * FROM quiz_logs ORDER BY answered_at DESC", conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("term_logs"):
        df = pd.read_sql("SELECT * FROM term_logs ORDER BY viewed_at DESC", conn)
        st.dataframe(df, use_container_width=True)

with tab2:
    st.subheader("学生ごとの学習実績一覧")
    try:
        query_user = """
        SELECT 
            u.user_id AS 学籍番号,
            u.user_name AS 氏名,
            u.last_login AS 最終ログイン,
            COUNT(q.id) AS 解答問題数,
            SUM(COALESCE(q.is_correct, 0)) AS 正解数,
            ROUND(AVG(COALESCE(q.is_correct, 0)) * 100, 1) AS 正答率_パーセント
        FROM users u
        LEFT JOIN quiz_logs q ON u.user_id = q.user_id
        GROUP BY u.user_id
        """
        df_user = pd.read_sql(query_user, conn)
        st.dataframe(df_user, use_container_width=True)
    except Exception:
        st.info("ユーザーログはまだありません。")

with tab3:
    st.subheader("予想問題の正解記号（ア・イ・ウ・エ）の偏り分析")
    try:
        df_ans_dist = pd.read_sql("""
        SELECT correct_ans AS 正解記号, COUNT(*) AS 件数
        FROM questions
        GROUP BY correct_ans
        ORDER BY correct_ans
        """, conn)
        if not df_ans_dist.empty:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.dataframe(df_ans_dist, use_container_width=True)
            with c2:
                st.bar_chart(df_ans_dist.set_index("正解記号"))
        else:
            st.info("出題対象の問題データがありません。")
    except Exception:
        st.info("問題データを集計できませんでした。")

with tab4:
    st.subheader("学習行動シーケンス（時系列ログ）")
    try:
        df_seq = pd.read_sql("""
        SELECT user_id AS ユーザーID, '用語閲覧' AS 行動, term_name AS 対象, viewed_at AS 日時 FROM term_logs
        UNION ALL
        SELECT user_id AS ユーザーID, '問題解答' AS 行動, term_name AS 対象, answered_at AS 日時 FROM quiz_logs
        ORDER BY 日時 DESC LIMIT 100
        """, conn)
        st.dataframe(df_seq, use_container_width=True)

        if not df_seq.empty:
            csv_data = df_seq.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 行動ログをCSVダウンロード（研究分析用）",
                data=csv_data,
                file_name="fe_learning_logs.csv",
                mime="text/csv"
            )
    except Exception:
        st.info("行動ログなし")

conn.close()