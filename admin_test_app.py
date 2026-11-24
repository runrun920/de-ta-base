import streamlit as st
import pandas as pd
import os
import base64
import requests
import io

# ---------------------------------------------------------
# 1. 基本設定
# ---------------------------------------------------------
st.set_page_config(page_title="FE-AI Tutor | 管理者ダッシュボード", page_icon="📊", layout="wide")

LOG_FILE = "test_app.log"
ADMIN_PASSWORD = "admin"  # 必要に応じてパスワードを変更してください

def fetch_github_file(path):
    """GitHubリポジトリからテキスト/CSVファイルの内容を取得する共通関数"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        branch = st.secrets.get("GITHUB_BRANCH", "test")

        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get(url, headers=headers, params={"ref": branch}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            content = base64.b64decode(data["content"]).decode("utf-8-sig")
            return content, "GitHub"
        elif res.status_code == 404:
            return None, "未作成"
        else:
            return None, f"Error ({res.status_code})"
    except Exception:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
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
# 4. データ取得＆集計処理（GitHub連携）
# ---------------------------------------------------------
st.title("📊 効果検証システム 管理者用データ一覧")

results_csv, _ = fetch_github_file("test_results.csv")
logs_csv, _ = fetch_github_file("test_logs.csv")

df_summary = pd.DataFrame()
if results_csv:
    df_res = pd.read_csv(io.StringIO(results_csv), dtype={"学籍番号_ID": str})
    if not df_res.empty:
        # 同一ユーザー・同一テスト種別で複数回ある場合は最新を採用
        df_res_latest = df_res.drop_duplicates(subset=["学籍番号_ID", "テスト種別"], keep="last")
        
        users_info = df_res.groupby("学籍番号_ID", as_index=False).agg({
            "アカウント名": "last",
            "専攻": "last",
            "完了日時": "max"
        }).rename(columns={"完了日時": "最終受験日時"})

        pre_df = df_res_latest[df_res_latest["テスト種別"] == "事前テスト"][["学籍番号_ID", "点数", "正答率"]].rename(
            columns={"点数": "事前点数", "正答率": "事前正答率"}
        )
        post_df = df_res_latest[df_res_latest["テスト種別"] == "事後テスト"][["学籍番号_ID", "点数", "正答率"]].rename(
            columns={"点数": "事後点数", "正答率": "事後正答率"}
        )

        df_summary = users_info.merge(pre_df, on="学籍番号_ID", how="left").merge(post_df, on="学籍番号_ID", how="left")
        df_summary["事前テスト状況"] = df_summary["事前点数"].apply(lambda x: "✅ 受験済" if pd.notna(x) else "❌ 未受験")
        df_summary["事後テスト状況"] = df_summary["事後点数"].apply(lambda x: "✅ 受験済" if pd.notna(x) else "❌ 未受験")
        df_summary["点数変化"] = df_summary["事後点数"] - df_summary["事前点数"]

        # 列の並び順を整理
        cols_order = [
            "学籍番号_ID", "アカウント名", "専攻", "最終受験日時",
            "事前テスト状況", "事前点数", "事前正答率",
            "事後テスト状況", "事後点数", "事後正答率", "点数変化"
        ]
        df_summary = df_summary[cols_order].sort_values(by="最終受験日時", ascending=False)

# サマリー指標（KPI）の表示
if not df_summary.empty:
    total_users = len(df_summary)
    pre_done = len(df_summary[df_summary["事前テスト状況"] == "✅ 受験済"])
    post_done = len(df_summary[df_summary["事後テスト状況"] == "✅ 受験済"])
    avg_pre = df_summary["事前点数"].mean()
    avg_post = df_summary["事後点数"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("総受験ユーザー数", f"{total_users} 名")
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
    if df_summary.empty:
        st.info("まだテスト完了データ（`test_results.csv`）がありません。被験者がテストを提出するとここに自動反映されます。")
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
    if not logs_csv:
        st.info("まだ詳細解答ログ（`test_logs.csv`）がありません。被験者がテストを提出するとここに自動反映されます。")
    else:
        st.subheader("全被験者の1問ごとの解答履歴")
        df_logs = pd.read_csv(io.StringIO(logs_csv), dtype={"学籍番号_ID": str})
        df_logs = df_logs.iloc[::-1]  # 新しい解答を上に表示

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
    log_path = st.secrets.get("LOG_FILE_PATH", LOG_FILE) if "LOG_FILE_PATH" in st.secrets else LOG_FILE
    log_content, source_type = fetch_github_file(log_path)

    if log_content is None:
        st.warning(f"ログファイルがまだ作成されていません（状態: {source_type}）。")
    else:
        st.caption(f"取得元: **{source_type}** ｜ 左サイドバーの「🔄 データを最新に更新」で最新のログを再読み込みできます。")

        log_filter = st.text_input("ログ内のキーワードで絞り込み検索：", placeholder="例: G23908 や TEST_COMPLETED")
        lines = log_content.splitlines()

        if log_filter.strip():
            lines = [line for line in lines if log_filter.strip() in line]

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
