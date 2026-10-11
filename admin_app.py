"""
FE-AI Tutor: 学習行動・研究データ分析ダッシュボード
卒業論文「第5章 評価実験および考察」分析用アナリティクス基盤
"""

import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(page_title="FE-AI Tutor 研究分析ダッシュボード", layout="wide", page_icon="📊")

st.markdown("""
<meta name="google" content="notranslate">
<style>
    html, body, [class*="css"], .stApp {
        translate: no !important;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
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
st.caption("適応型学習支援システムにおける学習者行動ログの分析と仮説検証（卒業論文 第5章 評価実験用）")

# ---------------------------------------------------------
# 全体サマリー指標
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)

try:
    all_users_cnt = pd.read_sql("SELECT COUNT(*) FROM users", conn).iloc[0, 0]
except Exception:
    all_users_cnt = 0

try:
    all_terms_cnt = pd.read_sql("SELECT COUNT(*) FROM terms", conn).iloc[0, 0]
except Exception:
    all_terms_cnt = 0

try:
    q_cnt = pd.read_sql("SELECT COUNT(*) FROM questions", conn).iloc[0, 0]
except Exception:
    q_cnt = 0

try:
    log_cnt = pd.read_sql("SELECT COUNT(*) FROM quiz_logs", conn).iloc[0, 0]
except Exception:
    log_cnt = 0

try:
    cv_cnt = pd.read_sql("SELECT COUNT(*) FROM content_view_logs", conn).iloc[0, 0]
except Exception:
    cv_cnt = 0

col1.metric("被験者数（登録学生）", f"{all_users_cnt} 名")
col2.metric("用語マスター数", f"{all_terms_cnt} 語")
col3.metric("収録問題数", f"{q_cnt} 問")
col4.metric("総解答ログ数", f"{log_cnt} 回")
col5.metric("コンテンツ閲覧ログ数", f"{cv_cnt} 回")

st.markdown("---")

tab_eval, tab_attr, tab_fields, tab_time, tab_raw = st.tabs([
    "🎓 卒論仮説検証サマリー（第5章用）",
    "👥 学習者属性別 行動・成績比較", 
    "📂 分野別 正答率・ボトルネック分析",
    "⏱️ 解答時間・タイムマネジメント分析",
    "🗄️ データベース全テーブル＆RAWログ出力"
])

# =========================================================
# TAB 1: 卒論仮説検証サマリー
# =========================================================
with tab_eval:
    st.subheader("🎓 卒業論文 第5章（評価実験）向け主要集計テーブル")
    st.caption("論文の本文や表（Table）にそのまま転記可能な集計結果です。")

    try:
        # 修正前: ROUND(...) AS 1人あたり演習数
        # 修正後: ROUND(...) AS "1人あたり演習数" （または 一人あたり演習数）
        query_hypo = """
        SELECT 
            COALESCE(u.major_type, '未設定') AS 履修区分,
            COUNT(DISTINCT u.user_id) AS 被験者数,
            COUNT(q.id) AS 総解答問題数,
            ROUND(AVG(COALESCE(q.is_correct, 0)) * 100, 1) AS 平均正答率_パーセント,
            ROUND(AVG(COALESCE(q.response_time_seconds, 0)), 1) AS 平均解答所要時間_秒,
            ROUND(COUNT(DISTINCT q.id) * 1.0 / NULLIF(COUNT(DISTINCT u.user_id), 0), 1) AS "1人あたり演習数"
        FROM users u
        LEFT JOIN quiz_logs q ON u.user_id = q.user_id
        GROUP BY u.major_type
        """
        df_hypo = pd.read_sql(query_hypo, conn)
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown("##### 表 5-1: 学習者属性別の解答パフォーマンス比較")
            st.dataframe(df_hypo, use_container_width=True)
        with c2:
            st.write("")
            csv_hypo = df_hypo.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 表5-1 をCSVダウンロード",
                data=csv_hypo,
                file_name="table_5_1_major_comparison.csv",
                mime="text/csv"
            )

        st.markdown("---")
        
        # コンテンツ閲覧種別（比喩 vs 実用例 vs 定義）の属性別閲覧数
        query_cv_attr = """
        SELECT 
            COALESCE(u.major_type, '未設定') AS 履修区分,
            SUM(CASE WHEN cv.content_type = 'metaphor' THEN 1 ELSE 0 END) AS 比喩_閲覧数,
            SUM(CASE WHEN cv.content_type = 'example' THEN 1 ELSE 0 END) AS 実例_閲覧数,
            SUM(CASE WHEN cv.content_type = 'official' THEN 1 ELSE 0 END) AS 公式定義_閲覧数,
            COUNT(cv.id) AS 総閲覧数
        FROM users u
        LEFT JOIN content_view_logs cv ON u.user_id = cv.user_id
        GROUP BY u.major_type
        """
        df_cv_attr = pd.read_sql(query_cv_attr, conn)
        
        c3, c4 = st.columns([3, 1])
        with c3:
            st.markdown("##### 表 5-2: 学習者属性別の多層解説アプローチ選択比率")
            st.dataframe(df_cv_attr, use_container_width=True)
        with c4:
            st.write("")
            csv_cv_attr = df_cv_attr.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 表5-2 をCSVダウンロード",
                data=csv_cv_attr,
                file_name="table_5_2_content_preference.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.info(f"集計データを作成できませんでした: {e}")

# =========================================================
# TAB 2: 学習者属性別 行動・成績比較
# =========================================================
with tab_attr:
    st.subheader("👥 学習者属性（文系・初学者 vs 情報科学科・理系）の詳細比較")

    try:
        df_user_detail = pd.read_sql("""
        SELECT 
            u.user_id AS 学籍番号,
            u.user_name AS 氏名,
            COALESCE(u.major_type, '未設定') AS 属性,
            u.last_login AS 最終ログイン,
            COUNT(q.id) AS 解答数,
            SUM(COALESCE(q.is_correct, 0)) AS 正解数,
            ROUND(AVG(COALESCE(q.is_correct, 0)) * 100, 1) AS 正答率,
            ROUND(AVG(COALESCE(q.response_time_seconds, 0)), 1) AS 平均解答秒
        FROM users u
        LEFT JOIN quiz_logs q ON u.user_id = q.user_id
        GROUP BY u.user_id
        ORDER BY 解答数 DESC
        """, conn)

        st.dataframe(df_user_detail, use_container_width=True)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("##### 属性別 正答率の分布比較")
            if not df_user_detail.empty and "属性" in df_user_detail.columns:
                chart_data = df_user_detail.groupby("属性")["正答率"].mean()
                st.bar_chart(chart_data)
        with col_g2:
            st.markdown("##### 属性別 平均解答所要時間の比較（秒）")
            if not df_user_detail.empty and "属性" in df_user_detail.columns:
                chart_time = df_user_detail.groupby("属性")["平均解答秒"].mean()
                st.bar_chart(chart_time)

    except Exception as e:
        st.info(f"属性データの読み込みエラー: {e}")

    st.markdown("---")
    st.subheader("⚠️ 被験者アカウント管理・データクリーンアップ")
    user_list = df_user_detail["学籍番号"].tolist() if ('df_user_detail' in locals() and not df_user_detail.empty) else []
    
    if user_list:
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            target_user = st.selectbox("削除対象の学籍番号を選択してください：", user_list)
        with col_btn:
            st.write("")
            if st.button("🗑️ アカウントおよび全ログを削除", type="primary"):
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE user_id = ?", (target_user,))
                cur.execute("DELETE FROM quiz_logs WHERE user_id = ?", (target_user,))
                cur.execute("DELETE FROM quiz_bookmarks WHERE user_id = ?", (target_user,))
                cur.execute("DELETE FROM term_logs WHERE user_id = ?", (target_user,))
                cur.execute("DELETE FROM content_view_logs WHERE user_id = ?", (target_user,))
                conn.commit()
                st.success(f"学籍番号 {target_user} の全データを削除しました。")
                st.rerun()

# =========================================================
# TAB 3: 分野別 正答率・ボトルネック分析
# =========================================================
with tab_fields:
    st.subheader("📂 シラバス分類別の正答率・所要時間分析（弱点ボトルネックの特定）")
    st.caption("正答率が低く所要時間が長い分野ほど、学習者にとって認知負荷が高い分野（要対策）と判断できます。")

    try:
        # 大分類・中分類とquiz_logsを結合
        query_fields = """
        SELECT 
            t.category AS 大分類,
            t.sub_category AS 中分類,
            COUNT(q.id) AS 演習実施数,
            SUM(COALESCE(q.is_correct, 0)) AS 正解数,
            ROUND(AVG(COALESCE(q.is_correct, 0)) * 100, 1) AS 正答率_パーセント,
            ROUND(AVG(COALESCE(q.response_time_seconds, 0)), 1) AS 平均解答時間_秒
        FROM quiz_logs q
        JOIN questions qs ON q.question_id = qs.id
        JOIN terms t ON qs.term_id = t.id
        GROUP BY t.sub_category
        ORDER BY 正答率_パーセント ASC, 平均解答時間_秒 DESC
        """
        df_fields = pd.read_sql(query_fields, conn)

        if not df_fields.empty:
            c_f1, c_f2 = st.columns([3, 1])
            with c_f1:
                st.dataframe(df_fields, use_container_width=True)
            with c_f2:
                csv_field = df_fields.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 分野別分析データをCSV保存",
                    data=csv_field,
                    file_name="table_field_bottlenecks.csv",
                    mime="text/csv"
                )

            st.markdown("##### 中分類別 正答率ワーストランキング（ボトルネック分野）")
            st.bar_chart(df_fields.set_index("中分類")["正答率_パーセント"])
        else:
            st.info("まだ分野分析に十分な問題演習ログがありません。")
    except Exception as e:
        st.info(f"分野別分析の実行中にエラーが発生しました: {e}")

# =========================================================
# TAB 4: 解答時間・タイムマネジメント分析
# =========================================================
with tab_time:
    st.subheader("⏱️ 解答時間（レスポンスタイム）と正誤の相関分析")
    st.caption("基本情報技術者試験（科目A）の基準時間（1問あたり90秒）に対する解答速度と正誤の分布を検証します。")

    try:
        # 修正前: SUM(...) AS 90秒超過問題数
        # 修正後: SUM(...) AS "90秒超過問題数" （または 超過問題数_90秒）
        query_resp = """
        SELECT 
            CASE is_correct WHEN 1 THEN '✅ 正解' ELSE '❌ 不正解' END AS 正誤区分,
            COUNT(*) AS 解答数,
            ROUND(AVG(response_time_seconds), 1) AS 平均解答時間_秒,
            ROUND(MIN(response_time_seconds), 1) AS 最短解答秒,
            ROUND(MAX(response_time_seconds), 1) AS 最長解答秒,
            SUM(CASE WHEN response_time_seconds > 90 THEN 1 ELSE 0 END) AS "90秒超過問題数"
        FROM quiz_logs
        GROUP BY is_correct
        """
        df_resp = pd.read_sql(query_resp, conn)
        st.dataframe(df_resp, use_container_width=True)

        st.markdown("##### 直近の解答所要時間（秒）の推移")
        df_time_series = pd.read_sql("""
        SELECT id AS 解答ID, response_time_seconds AS 所要時間_秒 
        FROM quiz_logs ORDER BY answered_at DESC LIMIT 50
        """, conn)
        if not df_time_series.empty:
            st.line_chart(df_time_series.set_index("解答ID"))

    except Exception as e:
        st.info(f"時間分析データの読み込みエラー: {e}")

# =========================================================
# TAB 5: データベース全テーブル＆RAWログ出力
# =========================================================
with tab_raw:
    st.subheader("🗄️ 全データベーステーブルの生データ確認＆CSVエクスポート")

    table_choice = st.selectbox(
        "テーブル・ビューを選択：",
        [
            "quiz_logs (TABLE: 問題解答・タイムログ)",
            "content_view_logs (TABLE: コンテンツ種別閲覧ログ)",
            "users (TABLE: 学生アカウント)",
            "quiz_bookmarks (TABLE: 弱点要復習ブックマーク)",
            "terms_master (VIEW: 全結合ビュー)",
            "terms (TABLE: 用語・公式定義)",
            "term_metaphors (TABLE: 比喩・例え話)",
            "term_examples (TABLE: 身近な実用例)",
            "questions (TABLE: 4択問題マスター)",
            "term_logs (TABLE: 用語全体閲覧ログ)"
        ]
    )

    t_name_clean = table_choice.split(" ")[0]
    try:
        df_raw = pd.read_sql(f"SELECT * FROM {t_name_clean}", conn)
        st.write(f"▼ `{t_name_clean}` 総レコード数: **{len(df_raw)}** 件")
        st.dataframe(df_raw, use_container_width=True)

        csv_raw_data = df_raw.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label=f"📥 {t_name_clean} をCSVダウンロード",
            data=csv_raw_data,
            file_name=f"{t_name_clean}_export.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"テーブル表示エラー: {e}")

conn.close()