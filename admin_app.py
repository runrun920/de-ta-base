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
    st.error("⚠️ データベース（fe_study.db）が見つかりません。")
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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗄️ データベース全テーブル閲覧",
    "👤 学生別 学習進捗・正答率", 
    "👁️ コンテンツ閲覧分析（例え話・実用例）",
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
            "content_view_logs (TABLE: コンテンツ種別閲覧ログ)",
            "quiz_logs (TABLE: 問題解答ログ)",
            "term_logs (TABLE: 用語全体閲覧ログ)"
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
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("term_examples"):
        df = pd.read_sql("""
        SELECT e.id, t.term_name AS 用語名, e.example_text AS 身近な実用例, e.source_ai AS 作成元
        FROM term_examples e
        JOIN terms t ON e.term_id = t.id
        """, conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("questions"):
        df = pd.read_sql("""
        SELECT q.id, t.term_name AS 用語名, q.question_text AS 問題文, q.choice_a, q.choice_b, q.choice_c, q.choice_d, q.correct_ans AS 正解
        FROM questions q
        JOIN terms t ON q.term_id = t.id
        """, conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("question_explanations_beginner"):
        df = pd.read_sql("""
        SELECT qeb.id, qeb.question_id, q.question_text AS 対象問題, qeb.explanation AS 文系初学者向け解説
        FROM question_explanations_beginner qeb
        JOIN questions q ON qeb.question_id = q.id
        """, conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("question_explanations_advanced"):
        df = pd.read_sql("""
        SELECT qea.id, qea.question_id, q.question_text AS 対象問題, qea.explanation AS 情報科学科向け解説
        FROM question_explanations_advanced qea
        JOIN questions q ON qea.question_id = q.id
        """, conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("term_categories"):
        df = pd.read_sql("SELECT * FROM term_categories", conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("users"):
        df = pd.read_sql("SELECT * FROM users", conn)
        st.dataframe(df, use_container_width=True)

    elif table_choice.startswith("content_view_logs"):
        try:
            df = pd.read_sql("SELECT * FROM content_view_logs ORDER BY viewed_at DESC", conn)
            st.dataframe(df, use_container_width=True)
        except Exception:
            st.info("content_view_logs テーブルはまだ空です。")

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

        st.markdown("---")
        st.subheader("⚠️ アカウント管理・データクリーンアップ")
        user_list = df_user["学籍番号"].tolist() if not df_user.empty else []
        
        if user_list:
            col_sel, col_btn = st.columns([3, 1])
            with col_sel:
                target_user = st.selectbox("削除対象の学籍番号を選択してください：", user_list)
            with col_btn:
                st.write("")
                if st.button("🗑️ アカウントを削除", type="primary"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM users WHERE user_id = ?", (target_user,))
                    cur.execute("DELETE FROM quiz_logs WHERE user_id = ?", (target_user,))
                    cur.execute("DELETE FROM term_logs WHERE user_id = ?", (target_user,))
                    cur.execute("DELETE FROM content_view_logs WHERE user_id = ?", (target_user,))
                    conn.commit()
                    st.success(f"学籍番号 {target_user} のアカウントおよび全ログを削除しました。")
                    st.rerun()
        else:
            st.info("登録されている学生はいません。")
    except Exception:
        st.info("ユーザーログはまだありません。")

with tab3:
    st.subheader("👁️ コンテンツ種別ごとの閲覧頻度分析")
    st.caption("学生が「例え話」「実用例」「公式定義」のどれをどれくらい閲覧したかを可視化します。")
    try:
        df_cv_summary = pd.read_sql("""
        SELECT 
            CASE content_type
                WHEN 'metaphor' THEN '💡 直感理解（例え話）'
                WHEN 'example' THEN '🌍 身近な実用例'
                WHEN 'official' THEN '📖 試験対策（公式定義）'
                ELSE content_type
            END AS コンテンツ種別,
            COUNT(*) AS 閲覧回数
        FROM content_view_logs
        GROUP BY content_type
        ORDER BY 閲覧回数 DESC
        """, conn)

        if not df_cv_summary.empty:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.dataframe(df_cv_summary, use_container_width=True)
            with c2:
                st.bar_chart(df_cv_summary.set_index("コンテンツ種別"))

            st.markdown("---")
            st.subheader("学生別の閲覧傾向")
            df_cv_user = pd.read_sql("""
            SELECT 
                user_id AS 学籍番号,
                SUM(CASE WHEN content_type='metaphor' THEN 1 ELSE 0 END) AS 例え話閲覧数,
                SUM(CASE WHEN content_type='example' THEN 1 ELSE 0 END) AS 実用例閲覧数,
                SUM(CASE WHEN content_type='official' THEN 1 ELSE 0 END) AS 公式定義閲覧数,
                COUNT(*) AS 合計閲覧数
            FROM content_view_logs
            GROUP BY user_id
            """, conn)
            st.dataframe(df_cv_user, use_container_width=True)
        else:
            st.info("まだ詳細なコンテンツ閲覧ログはありません。アプリで用語学習を行うとここに記録されます。")
    except Exception:
        st.info("閲覧ログテーブルはまだ生成されていません。")

with tab4:
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

with tab5:
    st.subheader("学習行動シーケンス（時系列ログ）")
    try:
        df_seq = pd.read_sql("""
        SELECT 
            user_id AS ユーザーID, 
            CASE content_type
                WHEN 'metaphor' THEN '例え話閲覧'
                WHEN 'example' THEN '実用例閲覧'
                WHEN 'official' THEN '公式定義閲覧'
                ELSE '用語閲覧'
            END AS 行動,
            term_name AS 対象, 
            viewed_at AS 日時 
        FROM content_view_logs
        UNION ALL
        SELECT user_id AS ユーザーID, '問題解答' AS 行動, term_name AS 対象, answered_at AS 日時 FROM quiz_logs
        ORDER BY 日時 DESC LIMIT 100
        """, conn)
        st.dataframe(df_seq, use_container_width=True)

        if not df_seq.empty:
            csv_data = df_seq.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 詳細行動ログをCSVダウンロード（研究分析用）",
                data=csv_data,
                file_name="fe_learning_detailed_logs.csv",
                mime="text/csv"
            )
    except Exception:
        st.info("行動ログなし")

conn.close()