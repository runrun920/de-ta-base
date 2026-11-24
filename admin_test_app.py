import streamlit as st
import sqlite3
import pandas as pd
import os
import base64
import requests

# ---------------------------------------------------------
# 1. 基本設定
# ---------------------------------------------------------
st.set_page_config(page_title="FE-AI Tutor | 管理者ダッシュボード", page_icon="📊", layout="wide")

DB_FILE = "fe_study.db"
LOG_FILE = "test_app.log"
ADMIN_PASSWORD = "admin"  # 必要に応じてパスワードを変更してください

def get_db():
    return sqlite3.connect(DB_FILE)

def fetch_github_log():
    """GitHubリポジトリから最新のログファイルを取得（未設定時はローカルを参照）"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        branch = st.secrets.get("GITHUB_BRANCH", "test")
        path = st.secrets.get("LOG_FILE_PATH", "test_app.log")

        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get(url, headers=headers, params={"ref": branch}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, "GitHub"
        elif res.status_code == 404:
            return None, "GitHub（ファイル未作成）"
        else:
            return f"GitHub取得エラー (Status: {res.status_code})", "Error"
    except Exception:
        # ローカル環境などSecrets未設定時はローカルのlogファイルを読む
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return f.read(), "ローカル"
        return None, "未設定"

# ---------------------------------------------------------
# 2. 簡易認証（被験者による誤アクセス防止）
# ---------------------------------------------------------
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if not st.session_state.admin_authenticated:
    st.title("🔒 管理者用ダッシュボード ログイン")
    col1, _ = st.columns([1, 2])
    with col1:
        pwd = st.text_input("管理者パスワードを入力してください：", type="password")
        if st.button("ログイン", type="primary"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
    st.stop()

# ---------------------------------------------------------
# 3. サイドバー
# ---------------------------------------------------------
with st.sidebar:
    st.header("🛠️ 管理者メニュー")
    if st.button("🔄 データを最新に更新", use_container_width=True):
        st.rerun()
    
    st.markdown("---")
    if st.button("ログアウト", use_container_width=True):
        st.session_state.admin_authenticated = False
        st.rerun()

# ---------------------------------------------------------
# 4. データ取得処理
# ---------------------------------------------------------
st.title("📊 効果検証システム 管理者用データ一覧")

has_db = os.path.exists(DB_FILE)

if has_db:
    conn = get_db()

    query_summary = """
    SELECT 
        u.user_id AS 学籍番号_ID,
        u.user_name AS アカウント名,
        u.last_login AS 最終ログイン日時,
        CASE WHEN pre.score IS NOT NULL THEN '✅ 受験済' ELSE '❌ 未受験' END AS 事前テスト状況,
        pre.score AS 事前点数,
        pre.accuracy_rate AS 事前正答率,
        CASE WHEN post.score IS NOT NULL THEN '✅ 受験済' ELSE '❌ 未受験' END AS 事後テスト状況,
        post.score AS 事後点数,
        post.accuracy_rate AS 事後正答率,
        (post.score - pre.score) AS 点数変化
    FROM users u
    LEFT JOIN test_results pre ON u.user_id = pre.user_id AND pre.test_type = '事前テスト'
    LEFT JOIN test_results post ON u.user_id = post.user_id AND post.test_type = '事後テスト'
    ORDER BY u.last_login DESC
    """
    df_summary = pd.read_sql(query_summary, conn)

    query_logs = """
    SELECT 
        l.answered_at AS 解答日時,
        l.user_id AS 学籍番号_ID,
        u.user_name AS アカウント名,
        l.test_type AS テスト種別,
        l.sub_category AS 分野,
        l.term_name AS 対象用語,
        l.selected_choice AS 選択解答,
        l.correct_ans AS 正解,
        CASE WHEN l.is_correct = 1 THEN '○' ELSE '×' END AS 正誤
    FROM test_logs l
    LEFT JOIN users u ON l.user_id = u.user_id
    ORDER BY l.id DESC
    """
    df_logs = pd.read_sql(query_logs, conn)
    conn.close()

    # サマリー指標（KPI）の表示
    total_users = len(df_summary)
    pre_done = len(df_summary[df_summary["事前テスト状況"] == "✅ 受験済"])
    post_done = len(df_summary[df_summary["事後テスト状況"] == "✅ 受験済"])
    avg_pre = df_summary["事前点数"].mean()
    avg_post = df_summary["事後点数"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("総登録ユーザー数", f"{total_users} 名")
    col2.metric("事前テスト完了", f"{pre_done} / {total_users} 名")
    col3.metric("事後テスト完了", f"{post_done} / {total_users} 名")
    col4.metric("事前テスト平均点", f"{avg_pre:.1f} 点" if pd.notna(avg_pre) else "-")
    col5.metric("事後テスト平均点", f"{avg_post:.1f} 点" if pd.notna(avg_post) else "-")

    st.markdown("---")

# ---------------------------------------------------------
# 5. タブ切り替えによる一覧表示＆CSV/ログ出力
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📋 被験者別 受験状況・スコア一覧",
    "🔍 問題別 詳細解答ログ",
    "📜 操作ログ（GitHub連携）"
])

with tab1:
    if not has_db:
        st.info("現在このサーバー内にローカルDB（`fe_study.db`）は存在しません。操作ログは右の「📜 操作ログ（GitHub連携）」タブから確認できます。")
    else:
        st.subheader("被験者ごとの受験ステータスと点数")
        filter_status = st.radio(
            "表示絞り込み：",
            ["すべて表示", "両方完了（事前・事後）", "事後テスト未受験のみ", "事前テスト未受験のみ"],
            horizontal=True
        )
        
        df_filtered = df_summary.copy()
        if filter_status == "両方完了（事前・事後）":
            df_filtered = df_filtered[(df_filtered["事前テスト状況"] == "✅ 受験済") & (df_filtered["事後テスト状況"] == "✅ 受験済")]
        elif filter_status == "事後テスト未受験のみ":
            df_filtered = df_filtered[df_filtered["事後テスト状況"] == "❌ 未受験"]
        elif filter_status == "事前テスト未受験のみ":
            df_filtered = df_filtered[df_filtered["事前テスト状況"] == "❌ 未受験"]

        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                "事前点数": st.column_config.NumberColumn("事前点数 (10点満点)", format="%d 点"),
                "事後点数": st.column_config.NumberColumn("事後点数 (10点満点)", format="%d 点"),
                "事前正答率": st.column_config.NumberColumn("事前正答率", format="%.1f %%"),
                "事後正答率": st.column_config.NumberColumn("事後正答率", format="%.1f %%"),
                "点数変化": st.column_config.NumberColumn("スコア伸び幅", format="%+d 点"),
            }
        )

        csv_summary = df_filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 この一覧をCSVでダウンロード（Excel分析用）",
            data=csv_summary,
            file_name="fe_test_summary.csv",
            mime="text/csv",
            type="primary"
        )

with tab2:
    if not has_db:
        st.info("現在このサーバー内にローカルDB（`fe_study.db`）は存在しません。")
    else:
        st.subheader("全被験者の1問ごとの解答履歴")
        search_user = st.text_input("学籍番号またはアカウント名で検索：", placeholder="例: G23937 または 奥田")
        df_logs_filtered = df_logs.copy()
        if search_user.strip():
            df_logs_filtered = df_logs_filtered[
                df_logs_filtered["学籍番号_ID"].str.contains(search_user, na=False) |
                df_logs_filtered["アカウント名"].str.contains(search_user, na=False)
            ]

        st.dataframe(df_logs_filtered, use_container_width=True, hide_index=True)

        csv_logs = df_logs_filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 詳細ログをCSVでダウンロード",
            data=csv_logs,
            file_name="fe_test_detail_logs.csv",
            mime="text/csv"
        )

with tab3:
    st.subheader("📜 システム操作ログ（test_app.log）")
    log_content, source_type = fetch_github_log()

    if log_content is None:
        st.warning(f"ログファイルがまだ作成されていません（参照先: {source_type}）。被験者がテスト画面でログインすると自動的に作成されます。")
    else:
        st.caption(f"取得元: **{source_type}** ｜ 左サイドバーの「🔄 データを最新に更新」で最新のログを再読み込みできます。")

        # 学籍番号やイベント名での絞り込み検索
        log_filter = st.text_input("ログ内のキーワードで絞り込み検索：", placeholder="例: G23908 や TEST_COMPLETED")
        lines = log_content.splitlines()

        if log_filter.strip():
            lines = [line for line in lines if log_filter.strip() in line]

        # 新しいログが上に来るように逆順表示（古い順がいい場合は [::-1] を消してください）
        display_text = "\n".join(reversed(lines))

        st.text_area(
            f"表示件数: {len(lines)} 行（新しい順）",
            value=display_text,
            height=400
        )

        st.download_button(
            label="📥 ログファイル（test_app.log）をダウンロード",
            data=log_content.encode("utf-8"),
            file_name="test_app.log",
            mime="text/plain",
            type="primary"
        )
