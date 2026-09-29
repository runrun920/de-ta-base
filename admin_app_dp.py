import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(page_title="FE-AI Tutor 管理者ダッシュボード", layout="wide", page_icon="📊")

# 翻訳ツールの誤作動防止
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
st.caption("被験者（学生）の学習ログや、データベース（fe_study.db）の蓄積データ・問題バランスを検証できます。")

# サマリー集計
col1, col2, col3, col4 = st.columns(4)

try:
    tm_cnt = pd.read_sql("SELECT COUNT(*) FROM terms_master WHERE question_text IS NOT NULL AND question_text != ''", conn).iloc[0, 0]
except Exception:
    tm_cnt = 0

try:
    all_terms_cnt = pd.read_sql("SELECT COUNT(*) FROM terms", conn).iloc[0, 0]
except Exception:
    all_terms_cnt = 0

try:
    u_cnt = pd.read_sql("SELECT COUNT(*) FROM users", conn).iloc[0, 0]
except Exception:
    u_cnt = 0

try:
    log_cnt = pd.read_sql("SELECT COUNT(*) FROM quiz_logs", conn).iloc[0, 0]
except Exception:
    log_cnt = 0

col1.metric("総登録用語数（辞書）", f"{all_terms_cnt} 語")
col2.metric("特製演習問題（terms_master）", f"{tm_cnt} 問")
col3.metric("登録学生数", f"{u_cnt} 人")
col4.metric("総解答ログ数", f"{log_cnt} 回")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "🗄️ データベース全データ閲覧",
    "👤 学生別 学習進捗・正答率", 
    "⚖️ 問題バランス・正解分布検証", 
    "📈 学習行動シーケンス・ログ出力"
])

# --- TAB 1: データベース閲覧 ---
with tab1:
    st.subheader("データベース（fe_study.db）の中身")
    
    table_choice = st.selectbox(
        "確認したいテーブルを選択してください：",
        [
            "terms_master（特製コンテンツ：比喩・実例・4択問題・属性別解説）",
            "terms（過去問道場アーカイブ全3,300語）",
            "term_categories（シラバス23中分類マッピング）",
            "users（利用者マスター）",
            "quiz_logs（問題演習ログ）",
            "term_logs（用語閲覧ログ）"
        ]
    )
    
    if table_choice.startswith("terms_master"):
        try:
            df_tm = pd.read_sql("""
            SELECT 
                id, term_name AS 用語名, category AS 大分類, sub_category AS 中分類,
                official_def AS 公式定義, intuitive_def AS 例え話, practical_example AS 実用例,
                question_text AS 予想問題, choice_a AS ア, choice_b AS イ, choice_c AS ウ, choice_d AS エ, correct_ans AS 正解,
                explanation_beginner AS 文系向け解説,
                explanation_advanced AS 情報科学科向け解説
            FROM terms_master
            """, conn)
            st.success(f"▼ terms_master 登録件数：{len(df_tm)} 件")
            st.dataframe(df_tm, use_container_width=True)
        except Exception as e:
            st.warning("terms_master テーブルの読み込みに失敗しました。`python3 build_db.py` を実行してください。")

    elif table_choice.startswith("terms（"):
        df_terms = pd.read_sql("SELECT id, term_name AS 用語名, category AS 大分類, sub_category AS 中分類, official_def AS 公式解説, url AS 元URL FROM terms", conn)
        st.write(f"▼ 登録件数：{len(df_terms)} 件")
        st.dataframe(df_terms, use_container_width=True)

    elif table_choice.startswith("term_categories"):
        df_cat = pd.read_sql("SELECT * FROM term_categories", conn)
        st.write(f"▼ 登録件数：{len(df_cat)} 件")
        st.dataframe(df_cat, use_container_width=True)

    elif table_choice.startswith("users"):
        df_u = pd.read_sql("SELECT user_id AS 学籍番号, user_name AS 氏名, last_login AS 最終ログイン日時 FROM users", conn)
        st.dataframe(df_u, use_container_width=True)

    elif table_choice.startswith("quiz_logs"):
        df_ql = pd.read_sql("SELECT id, user_id AS 学籍番号, question_id AS 問題ID, term_name AS 用語名, selected_choice AS 選択, is_correct AS 正否, answered_at AS 解答日時 FROM quiz_logs ORDER BY answered_at DESC", conn)
        st.dataframe(df_ql, use_container_width=True)

    elif table_choice.startswith("term_logs"):
        df_tl = pd.read_sql("SELECT id, user_id AS 学籍番号, term_name AS 閲覧用語, category AS 分野, viewed_at AS 閲覧日時 FROM term_logs ORDER BY viewed_at DESC", conn)
        st.dataframe(df_tl, use_container_width=True)

# --- TAB 2: 学生別進捗 ---
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

# --- TAB 3: 正解分布検証 ---
with tab3:
    st.subheader("予想問題の正解記号（ア・イ・ウ・エ）の偏り分析")
    st.write("LLM（GPT/Gemini）生成時に生じやすい選択肢の偏りをチェックできます。")
    try:
        df_ans_dist = pd.read_sql("""
        SELECT correct_ans AS 正解記号, COUNT(*) AS 件数
        FROM terms_master
        WHERE question_text IS NOT NULL AND question_text != ''
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
    except Exception as e:
        st.info("問題データを集計できませんでした。")

# --- TAB 4: 時系列ログ & 出力 ---
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