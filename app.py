"""
FE-AI Tutor: 基本情報技術者試験（科目A）適応型学習支援システム
学部卒業論文 研究用実装コード
"""

import streamlit as st
import sqlite3
import random
import os
import logging
import re
import time
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd

# ---------------------------------------------------------
# ページ基本設定 & 多言語自動翻訳の抑止
# ---------------------------------------------------------
st.set_page_config(
    page_title="FE-AI Tutor - 適応型学習支援システム",
    page_icon="🎓",
    layout="wide"
)

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
LOG_FILE = "app.log"

# ---------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------
def setup_logger() -> logging.Logger:
    logger = logging.getLogger("FE_TUTOR_LOGGER")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

logger = setup_logger()

def get_db():
    return sqlite3.connect(DB_FILE)

if not os.path.exists(DB_FILE):
    st.error("⚠️ データベース（fe_study.db）が見つかりません。")
    st.info("ターミナルで `python3 sync_db.py` を実行してください。")
    st.stop()

# ---------------------------------------------------------
# データベーススキーマ自動拡張（卒論テレメトリ用）
# ---------------------------------------------------------
def init_extended_tables():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            last_login DATETIME
        )
        """)
        
        cur.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cur.fetchall()]
        if "major_type" not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN major_type TEXT DEFAULT '文系・初学者'")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            question_id INTEGER,
            term_name TEXT,
            selected_choice TEXT,
            is_correct INTEGER,
            answered_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("PRAGMA table_info(quiz_logs)")
        q_columns = [col[1] for col in cur.fetchall()]
        if "response_time_seconds" not in q_columns:
            cur.execute("ALTER TABLE quiz_logs ADD COLUMN response_time_seconds REAL DEFAULT 0.0")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            question_id INTEGER,
            term_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, question_id)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS content_view_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            term_name TEXT,
            content_type TEXT,
            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS term_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            term_name TEXT,
            category TEXT,
            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

init_extended_tables()

# ---------------------------------------------------------
# ドメイン定数定義（シラバス構造 & 過去問道場2,841問換算比率）
# ---------------------------------------------------------
SYLLABUS_STRUCTURE = {
    "テクノロジ系": [
        "1. 基礎理論", "2. アルゴリズムとプログラミング", "3. コンピュータ構成要素",
        "4. システム構成要素", "5. ソフトウェア", "6. ハードウェア",
        "7. ユーザーインタフェース", "8. 情報メディア", "9. データベース",
        "10. ネットワーク", "11. セキュリティ", "12. システム開発技術", "13. ソフトウェア開発管理技術"
    ],
    "マネジメント系": [
        "14. プロジェクトマネジメント", "15. サービスマネジメント", "16. システム監査"
    ],
    "ストラテジ系": [
        "17. システム戦略", "18. システム企画", "19. 経営戦略マネジメント",
        "20. 技術戦略マネジメント", "21. ビジネスインダストリ", "22. 企業活動", "23. 法務"
    ]
}

PAST_EXAM_WEIGHTS = {
    "基礎理論": 240, "アルゴリズムとプログラミング": 190, "コンピュータ構成要素": 200,
    "システム構成要素": 168, "ソフトウェア": 182, "ハードウェア": 63,
    "ユーザーインタフェース": 29, "情報メディア": 42, "データベース": 212,
    "ネットワーク": 197, "セキュリティ": 288, "システム開発技術": 179,
    "ソフトウェア開発管理技術": 57, "プロジェクトマネジメント": 120, "サービスマネジメント": 108,
    "システム監査": 81, "システム戦略": 101, "システム企画": 53,
    "経営戦略マネジメント": 108, "技術戦略マネジメント": 14, "ビジネスインダストリ": 101,
    "企業活動": 207, "法務": 101
}

def format_official_definition(raw_text: str) -> str:
    """
    過去問道場の公式定義テキストを整形し、
    読み・英語（同値または次行に値がある場合の両方に対応）を抽出し、
    分類タグを除去して改行付きで表示する
    """
    if not raw_text or str(raw_text).strip() in ["", "nan", "None"]:
        return ""
    
    text = str(raw_text).strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    reading = ""
    english = ""
    body_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 読みの判定
        if line.startswith("読み") and any(sep in line for sep in [":", "："]):
            val = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            if not val and i + 1 < len(lines):
                val = lines[i + 1].strip()
                i += 1
            reading = val
            i += 1
            continue
            
        # 英語の判定
        if line.startswith("英語") and any(sep in line for sep in [":", "："]):
            val = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            if not val and i + 1 < len(lines):
                val = lines[i + 1].strip()
                i += 1
            english = val
            i += 1
            continue
            
        # 分類タグ（数字開始の行 例: 5 ソフトウェア, 5-2 タスク管理）の除外
        first_word = line.split()[0] if line.split() else ""
        if any(first_word.startswith(f"{n}") for n in range(1, 24)):
            i += 1
            continue
            
        # 用語概要ヘッダー（例: "オペレーティングシステム - 82語...", "OS"）の除外
        if not body_lines and len(line) < 40 and not any(k in line for k in ["。", "、", "である", "です", "手法", "方式", "こと"]):
            i += 1
            continue
            
        body_lines.append(line)
        i += 1

    output = []
    if reading:
        output.append(f"**読み**： {reading}")
    if english:
        output.append(f"**英語**： {english}")
    if output and body_lines:
        output.append("---")
        
    if body_lines:
        output.append("\n\n".join(body_lines))
        
    return "\n\n".join(output) if output else text


def clean_subcat_name(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'^\d+\.\s*', '', str(name)).strip()

def split_summary_and_details(exp_text: str) -> Tuple[str, str]:
    if not exp_text or exp_text == "※解説準備中":
        return ("※解説準備中", "")

    split_patterns = [
        r'【各選択肢の解説】', r'【技術詳細と各選択肢】', 
        r'【技術詳細】', r'・【選択肢[アイウエ]】', 
        r'【[アイウエ]】', r'選択肢[アイウエ]', r'誤答の解説'
    ]
    
    split_pos = len(exp_text)
    for pat in split_patterns:
        m = re.search(pat, exp_text)
        if m and m.start() < split_pos:
            split_pos = m.start()

    summary_part = exp_text[:split_pos].strip()
    details_part = exp_text[split_pos:].strip()

    if not details_part and len(summary_part) > 80:
        sentences = re.split(r'(?<=。)\s*', exp_text)
        summary_part = "".join(sentences[:2]).strip()
        details_part = "".join(sentences[2:]).strip()

    if details_part:
        details_part = re.sub(r'\s*(【技術詳細と各選択肢】|【各選択肢の解説】)\s*', r'\1\n\n', details_part)
        details_part = re.sub(r'\s*(・?【選択肢[アイウエ]】:?)\s*', r'\n\n・\1 ', details_part)
        details_part = details_part.strip()

    return (summary_part, details_part)

def render_two_tier_explanation(exp_text: str, tab_label: str):
    summary_part, details_part = split_summary_and_details(exp_text)
    st.info(summary_part)
    if details_part:
        with st.expander(f"▼ 詳しい解説・各選択肢の理由をもっと見る（{tab_label}）"):
            st.markdown(details_part)

# ---------------------------------------------------------
# セッション状態の初期化
# ---------------------------------------------------------
defaults = {
    "logged_in": False,
    "user_id": "",
    "user_name": "",
    "major_type": "文系・初学者",
    "app_mode": "ホーム",
    "nav_selection": "🏠 ホーム",
    "current_term": "機密性",
    "quiz_active": False,
    "quiz_questions": [],
    "quiz_index": 0,
    "quiz_user_answers": {},
    "quiz_answered_current": False,
    "q_start_time": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------
# ログイン画面
# ---------------------------------------------------------
if not st.session_state.logged_in:
    st.markdown('<h1 translate="no">🎓 基本情報技術者試験 適応型学習支援システム (FE-AI Tutor)</h1>', unsafe_allow_html=True)
    st.caption("研究テーマ: 学習者プロファイルに適応したマルチモーダル解説と過去問比率再現による試験対策効果の検証")
    
    col1, _ = st.columns([1.2, 1])
    with col1:
        st.subheader("学習者認証")
        input_uid = st.text_input("学籍番号 または 実験用ID：", placeholder="例: G23937")
        input_name = st.text_input("お名前：", placeholder="例: 奥田 さえ")
        input_major = st.radio("履修背景・専攻区分を選択してください：", ["文系・初学者", "情報科学科・理系"], horizontal=True)
        
        if st.button("研究システムにログイン", type="primary"):
            if input_uid.strip() and input_name.strip():
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                    INSERT INTO users (user_id, user_name, major_type, last_login) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET last_login=CURRENT_TIMESTAMP, user_name=?, major_type=?
                    """, (input_uid.strip(), input_name.strip(), input_major, input_name.strip(), input_major))
                    conn.commit()
                
                st.session_state.logged_in = True
                st.session_state.user_id = input_uid.strip()
                st.session_state.user_name = input_name.strip()
                st.session_state.major_type = input_major
                
                logger.info(f"USER_LOGIN: user_id={input_uid.strip()}, major={input_major}")
                st.rerun()
            else:
                st.error("学籍番号とお名前を入力してください。")
    st.stop()

# ---------------------------------------------------------
# サイドバー
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div translate="no">👤 <b>{st.session_state.user_name}</b> さん<br><small>ID: {st.session_state.user_id} ｜ 属性: <b>{st.session_state.major_type}</b></small></div>', unsafe_allow_html=True)
    st.markdown("---")

    menu_options = ["🏠 ホーム", "📖 用語を勉強する", "📝 問題を解く", "⭐ 弱点復習リスト"]
    
    def on_nav_change():
        sel = st.session_state.nav_radio
        mode_map = {
            "🏠 ホーム": "ホーム",
            "📖 用語を勉強する": "用語を勉強する",
            "📝 問題を解く": "問題を解く",
            "⭐ 弱点復習リスト": "弱点復習リスト"
        }
        st.session_state.app_mode = mode_map[sel]
        st.session_state.nav_selection = sel
        if mode_map[sel] != "問題を解く":
            st.session_state.quiz_active = False

    target_idx = 0
    if st.session_state.app_mode == "用語を勉強する":
        target_idx = 1
    elif st.session_state.app_mode == "問題を解く":
        target_idx = 2
    elif st.session_state.app_mode == "弱点復習リスト":
        target_idx = 3

    st.radio("ナビゲーション：", menu_options, index=target_idx, key="nav_radio", on_change=on_nav_change)

    if st.session_state.app_mode == "用語を勉強する":
        st.markdown("---")
        st.subheader("🔍 用語探索")
        search_mode = st.radio("探索アプローチ：", ["キーワード検索", "シラバス分類から選択"])
        
        with get_db() as conn:
            cur = conn.cursor()
            if search_mode == "キーワード検索":
                try:
                    cur.execute("SELECT DISTINCT term_name FROM terms_master ORDER BY id")
                    ordered_terms = [r[0] for r in cur.fetchall()]
                except Exception:
                    ordered_terms = []

                kw = st.text_input("検索ワード：", placeholder="例: 機密性, RAID")
                matched = [t for t in ordered_terms if kw.strip().lower() in t.lower()] if kw.strip() else ordered_terms

                if matched:
                    def_idx = matched.index(st.session_state.current_term) if st.session_state.current_term in matched else 0
                    st.session_state.current_term = st.selectbox(f"合致用語（{len(matched)}件）：", options=matched, index=def_idx)
                else:
                    st.warning("該当用語が見つかりません。")

            elif search_mode == "シラバス分類から選択":
                c_sel = st.selectbox("1. 大分類：", list(SYLLABUS_STRUCTURE.keys()))
                s_sel = st.selectbox("2. 中分類：", SYLLABUS_STRUCTURE[c_sel])

                try:
                    cur.execute("SELECT DISTINCT term_name FROM terms_master WHERE sub_category = ?", (s_sel,))
                    f_terms = [r[0] for r in cur.fetchall()]
                except Exception:
                    f_terms = []

                if f_terms:
                    def_idx = f_terms.index(st.session_state.current_term) if st.session_state.current_term in f_terms else 0
                    st.session_state.current_term = st.selectbox(f"3. 対象用語（{len(f_terms)}件）：", options=f_terms, index=def_idx)
                else:
                    st.info(f"「{s_sel}」の登録用語は0件です。")

    st.markdown("---")
    col_out, col_del = st.columns(2)
    with col_out:
        if st.button("ログアウト", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.app_mode = "ホーム"
            st.session_state.quiz_active = False
            st.rerun()

    with col_del:
        with st.popover("データ削除", use_container_width=True):
            st.warning("自身のアカウントおよび全実験履歴を消去します。")
            if st.button("完全に削除", type="primary"):
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM users WHERE user_id = ?", (st.session_state.user_id,))
                    cur.execute("DELETE FROM quiz_logs WHERE user_id = ?", (st.session_state.user_id,))
                    cur.execute("DELETE FROM quiz_bookmarks WHERE user_id = ?", (st.session_state.user_id,))
                    cur.execute("DELETE FROM term_logs WHERE user_id = ?", (st.session_state.user_id,))
                    cur.execute("DELETE FROM content_view_logs WHERE user_id = ?", (st.session_state.user_id,))
                    conn.commit()
                st.session_state.logged_in = False
                st.rerun()

# ---------------------------------------------------------
# メイン画面：ホーム
# ---------------------------------------------------------
if st.session_state.app_mode == "ホーム":
    st.markdown(f'<h1 translate="no">ようこそ、{st.session_state.user_name} さん！ 👋</h1>', unsafe_allow_html=True)
    st.write("本システムは、学習者の属性に最適化されたマルチアプローチ解説と、出題傾向を模した出題ロジックを備えたFE試験学習システムです。")
    
    with get_db() as conn:
        df_p = pd.read_sql_query("""
        SELECT COUNT(id) as total_ans, SUM(is_correct) as correct_cnt, AVG(response_time_seconds) as avg_time
        FROM quiz_logs WHERE user_id = ?
        """, conn, params=(st.session_state.user_id,))
        ans_total = df_p["total_ans"].iloc[0] or 0
        cor_total = df_p["correct_cnt"].iloc[0] or 0
        avg_resp = df_p["avg_time"].iloc[0] or 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("総解答問題数", f"{ans_total} 問")
    c2.metric("累積正答率", f"{(cor_total / ans_total * 100):.1f}%" if ans_total > 0 else "0.0%")
    c3.metric("1問あたり平均思考時間", f"{avg_resp:.1f} 秒" if ans_total > 0 else "0.0 秒")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📖 多角的 用語学習\n初学者向けの「直感的比喩」、実務イメージを深める「実社会応用例」、IPAシラバスの「公式定義」の3層構造で概念理解を深めます。")
        if st.button("用語学習を始める ➔", key="btn_go_study", type="primary"):
            st.session_state.app_mode = "用語を勉強する"
            st.session_state.quiz_active = False
            st.rerun()
            
    with col2:
        st.success("### 📝 科目A 演習モード\n過去問道場の出題比率を反映した重み付け全分野演習、または特定中分類に絞った特訓演習が可能です。")
        if st.button("実戦問題演習へ進む ➔", key="btn_go_quiz", type="primary"):
            st.session_state.app_mode = "問題を解く"
            st.session_state.quiz_active = False
            st.rerun()

# ---------------------------------------------------------
# メイン画面：用語学習（3層マルチアプローチ ＋ イラスト図解）
# ---------------------------------------------------------
elif st.session_state.app_mode == "用語を勉強する":
    curr = st.session_state.current_term
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, category, sub_category, official_def, url, image_path FROM terms WHERE term_name = ?", (curr,))
        term_row = cur.fetchone()
        
        term_id = term_row[0] if term_row else None
        cat = term_row[1] if term_row else "テクノロジ系"
        sub_cat = term_row[2] if term_row else "未分類"
        off_def = term_row[3] if term_row else ""
        url = term_row[4] if term_row else ""
        img_path = term_row[5] if term_row and len(term_row) > 5 else None

        int_def = ""
        if term_id:
            cur.execute("SELECT metaphor_text FROM term_metaphors WHERE term_id = ? AND source_ai = 'Final'", (term_id,))
            m_row = cur.fetchone()
            if m_row:
                int_def = m_row[0]

        prac_ex = ""
        if term_id:
            cur.execute("SELECT example_text FROM term_examples WHERE term_id = ? AND source_ai = 'Final'", (term_id,))
            e_row = cur.fetchone()
            if e_row:
                prac_ex = e_row[0]

        cur.execute("INSERT INTO term_logs (user_id, term_name, category) VALUES (?, ?, ?)",
                    (st.session_state.user_id, curr, cat))
        conn.commit()

    st.caption(f"📚 {cat} ＞ {sub_cat}")
    st.markdown(f'<h1 translate="no">💻 {curr}</h1>', unsafe_allow_html=True)

    if img_path and os.path.exists(img_path):
        st.image(img_path, caption=f"🎨 イラストでわかる「{curr}」", use_container_width=True)

    view_choice = st.radio(
        "学習アプローチを選択してください（閲覧行動ログが研究データとして記録されます）：",
        ["💡 直感理解（日常の比喩）", "🌍 実社会での活用例", "📖 試験対策（公式定義）"],
        horizontal=True,
        key=f"view_choice_{curr}"
    )

    content_type_map = {
        "💡 直感理解（日常の比喩）": "metaphor",
        "🌍 実社会での活用例": "example",
        "📖 試験対策（公式定義）": "official"
    }
    selected_type = content_type_map[view_choice]

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO content_view_logs (user_id, term_name, content_type) VALUES (?, ?, ?)",
                    (st.session_state.user_id, curr, selected_type))
        conn.commit()

    if view_choice == "💡 直感理解（日常の比喩）":
        st.info(int_def if int_def else "💡 直感的比喩データは準備中です。")
    elif view_choice == "🌍 実社会での活用例":
        st.success(prac_ex if prac_ex else "🌍 実社会での活用例データは準備中です。")
    elif view_choice == "📖 試験対策（公式定義）":
        link_to_open = url
        if not link_to_open or str(link_to_open).strip() in ["", "nan", "None"]:
            import urllib.parse
            encoded_term = urllib.parse.quote(curr)
            link_to_open = f"https://www.fe-siken.com/keyword/{encoded_term}.html"
            
        st.markdown("### 📖 試験対策（公式定義）")
        st.caption(f"[🔗 過去問道場の関連ページを確認する]({link_to_open})")

# ---------------------------------------------------------
# メイン画面：問題演習モード
# ---------------------------------------------------------
elif st.session_state.app_mode == "問題を解く":
    st.markdown('<h1 translate="no">📝 科目A 実戦問題演習</h1>', unsafe_allow_html=True)

    # 演習設定画面
    if not st.session_state.quiz_active:
        st.subheader("演習セッションの設定")

        with get_db() as conn:
            cur = conn.cursor()
            quiz_mode = st.radio(
                "出題モードを選択：",
                ["🎲 全分野（科目Aの出題率準拠）", "📂 23分野別特訓（中分類指定）"],
                horizontal=True,
                key="quiz_mode_radio"
            )

            target_subcat = None
            if quiz_mode == "📂 23分野別特訓（中分類指定）":
                c1, c2 = st.columns(2)
                with c1:
                    c_sel_q = st.selectbox("大分類：", list(SYLLABUS_STRUCTURE.keys()), key="sel_cat")
                with c2:
                    s_sel_q = st.selectbox("中分類：", SYLLABUS_STRUCTURE[c_sel_q], key="sel_subcat")
                target_subcat = s_sel_q
                
                cur.execute("""
                SELECT COUNT(DISTINCT id) FROM terms_master 
                WHERE question_text IS NOT NULL AND question_text != '' AND sub_category = ?
                """, (target_subcat,))
                avail_q_count = cur.fetchone()[0]
                st.caption(f"「{target_subcat}」の出題可能数： **{avail_q_count}** 問")
            else:
                cur.execute("SELECT COUNT(DISTINCT id) FROM terms_master WHERE question_text IS NOT NULL AND question_text != ''")
                avail_q_count = cur.fetchone()[0]
                st.caption(f"全分野合計の出題可能数： **{avail_q_count}** 問")
                st.info("💡 **本番頻度配分モデル適用中**: テクノロジ約68%・マネジメント約12%・ストラテジ約20%の比率を保ち、出題実績の多い重要中分類から重み付けサンプリングします。")

        if avail_q_count == 0:
            st.warning("出題可能な問題がありません。先に `sync_db.py` でデータを同期してください。")
            st.stop()

        max_options = [cnt for cnt in [5, 10, 20, 60] if cnt < avail_q_count] + [avail_q_count]
        num_choice = st.radio(
            "出題数：", 
            max_options, 
            format_func=lambda x: f"{x}問 （全問演習）" if x == avail_q_count else f"{x}問", 
            horizontal=True,
            key="num_choice_radio"
        )

        if st.button("🚀 演習を開始する", type="primary", key="btn_start_quiz"):
            with get_db() as conn:
                if quiz_mode == "📂 23分野別特訓（中分類指定）":
                    cur = conn.cursor()
                    cur.execute("""
                    SELECT id, term_name, question_text, choice_a, choice_b, choice_c, choice_d, 
                           correct_ans, explanation_beginner, explanation_advanced, category, sub_category 
                    FROM terms_master 
                    WHERE question_text IS NOT NULL AND question_text != '' AND sub_category = ?
                    GROUP BY id
                    """, (target_subcat,))
                    raw_rows = cur.fetchall()
                    random.shuffle(raw_rows)
                    raw_selected = raw_rows[:num_choice]

                else:
                    df_all = pd.read_sql_query("""
                    SELECT id, term_name, question_text, choice_a, choice_b, choice_c, choice_d, 
                           correct_ans, explanation_beginner, explanation_advanced, category, sub_category 
                    FROM terms_master 
                    WHERE question_text IS NOT NULL AND question_text != ''
                    """, conn)

                    df_all = df_all.drop_duplicates(subset=["id"]).set_index("id", drop=False)
                    df_all["weight"] = df_all.apply(lambda r: PAST_EXAM_WEIGHTS.get(clean_subcat_name(r["sub_category"]), 30), axis=1)

                    if num_choice >= len(df_all):
                        df_selected = df_all.sample(frac=1).reset_index(drop=True)
                    else:
                        n_tech = int(round(num_choice * 0.68))
                        n_mgmt = int(round(num_choice * 0.12))
                        n_strat = num_choice - (n_tech + n_mgmt)

                        sampled_dfs = []
                        selected_indices = set()
                        for sub_df, needed in [
                            (df_all[df_all["category"] == "テクノロジ系"], n_tech),
                            (df_all[df_all["category"] == "マネジメント系"], n_mgmt),
                            (df_all[df_all["category"] == "ストラテジ系"], n_strat)
                        ]:
                            if needed <= 0 or len(sub_df) == 0:
                                continue
                            
                            if needed >= len(sub_df):
                                s = sub_df.copy()
                            else:
                                s = sub_df.sample(n=needed, weights="weight", replace=False)
                            
                            selected_indices.update(s.index.drop_duplicates().tolist())
                            sampled_dfs.append(s)

                        df_selected = pd.concat(sampled_dfs) if sampled_dfs else pd.DataFrame()
                        
                        if len(df_selected) < num_choice:
                            diff = num_choice - len(df_selected)
                            rem = df_all[~df_all.index.isin(selected_indices)]
                            if len(rem) > 0:
                                actual_add = min(diff, len(rem))
                                if actual_add >= len(rem):
                                    extra = rem.copy()
                                else:
                                    extra = rem.sample(n=actual_add, weights="weight", replace=False)
                                df_selected = pd.concat([df_selected, extra])

                        df_selected = df_selected.sample(frac=1).reset_index(drop=True)

                    raw_selected = [tuple(x) for x in df_selected[[
                        "id", "term_name", "question_text", "choice_a", "choice_b", 
                        "choice_c", "choice_d", "correct_ans", "explanation_beginner", 
                        "explanation_advanced", "category", "sub_category"
                    ]].values]

            st.session_state.quiz_questions = raw_selected
            st.session_state.quiz_index = 0
            st.session_state.quiz_user_answers = {}
            st.session_state.quiz_answered_current = False
            st.session_state.quiz_active = True
            st.session_state.q_start_time = time.time()
            st.rerun()

    # 演習実行画面
    else:
        q_list = st.session_state.quiz_questions
        idx = st.session_state.quiz_index
        total = len(q_list)

        # 演習完了画面
        if idx >= total:
            st.success("🎉 全問の解答が完了しました！")
            correct_count = sum(1 for a in st.session_state.quiz_user_answers.values() if a["is_correct"])
            rate = (correct_count / total) * 100 if total > 0 else 0
            avg_resp = sum(a.get("response_time", 0.0) for a in st.session_state.quiz_user_answers.values()) / total if total > 0 else 0.0

            c1, c2, c3 = st.columns(3)
            c1.metric("正答率", f"{rate:.1f}%", f"{correct_count} / {total} 問")
            c2.metric("合格判定（基準60%）", "合格水準達成 🏆" if rate >= 60.0 else "基準点未満 💡")
            c3.metric("平均解答所要時間", f"{avg_resp:.1f} 秒/問")

            if rate >= 60.0:
                st.balloons()

            st.markdown("---")
            st.subheader("📋 解答振り返り・属性別解説")
            for i, q in enumerate(q_list):
                q_id, q_term, q_text, c_a, c_b, c_c, c_d, c_ans, exp_beg, exp_adv, cat, sub_cat = q
                ans_data = st.session_state.quiz_user_answers.get(i, {})
                is_cor = ans_data.get("is_correct", False)
                sec_taken = ans_data.get("response_time", 0.0)

                with st.expander(f"問 {i+1}：{q_term}（{sub_cat}） — {'✅ 正解' if is_cor else '❌ 不正解'} （所要時間: {sec_taken:.1f}秒）"):
                    st.write(f"**問題：** {q_text}")
                    st.write(f"**あなたの解答：** {ans_data.get('selected')} ｜ **正解：** {c_ans}")
                    
                    t1, t2 = st.tabs(["🌱 初学者・文系向け解説", "🔬 情報科学科向け技術解説"])
                    with t1:
                        render_two_tier_explanation(exp_beg, "初学者・文系")
                    with t2:
                        render_two_tier_explanation(exp_adv, "情報科学科・理系")

            if st.button("🔄 新しい演習を開始する", type="primary"):
                st.session_state.quiz_active = False
                st.rerun()

        # 個別問題解答画面
        else:
            q = q_list[idx]
            q_id, q_term, q_text, c_a, c_b, c_c, c_d, c_ans, exp_beg, exp_adv, cat, sub_cat = q

            st.progress((idx + 1) / total)
            
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.caption(f"問題 {idx + 1} / {total} ｜ 出題分野: **{sub_cat}**")
            with col_h2:
                st.caption("⏱️ 推奨解答時間: 90秒以内")

            st.markdown(f'<h3 translate="no">Q{idx + 1}. {q_text}</h3>', unsafe_allow_html=True)

            choices = [f"ア: {c_a}", f"イ: {c_b}", f"ウ: {c_c}", f"エ: {c_d}"]
            user_choice = st.radio(
                "選択肢：", 
                choices, 
                key=f"q_radio_choice_{idx}", 
                disabled=st.session_state.quiz_answered_current
            )
            selected_char = user_choice[0]

            if not st.session_state.quiz_answered_current:
                if st.button("回答を送信する", type="primary", key=f"btn_submit_{idx}"):
                    elapsed_time = round(time.time() - (st.session_state.q_start_time or time.time()), 2)
                    is_correct = (selected_char == c_ans.strip())

                    st.session_state.quiz_user_answers[idx] = {
                        "question_id": q_id,
                        "selected": selected_char,
                        "is_correct": is_correct,
                        "response_time": elapsed_time
                    }
                    st.session_state.quiz_answered_current = True

                    with get_db() as conn:
                        cur = conn.cursor()
                        cur.execute("""
                        INSERT INTO quiz_logs (user_id, question_id, term_name, selected_choice, is_correct, response_time_seconds)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, q_id, q_term, selected_char, 1 if is_correct else 0, elapsed_time))
                        conn.commit()

                    st.rerun()

            else:
                ans_data = st.session_state.quiz_user_answers[idx]
                if ans_data["is_correct"]:
                    st.success(f"🎉 正解です！（正解：{c_ans} ｜ 解答時間: {ans_data['response_time']}秒）")
                else:
                    st.error(f"❌ 不正解です... あなたの回答：{ans_data['selected']}（正解：{c_ans} ｜ 解答時間: {ans_data['response_time']}秒）")

                col_info, col_bm = st.columns([3, 1])
                with col_info:
                    st.info(f"💡 出題対象用語: **{q_term}** （{cat} ＞ {sub_cat}）")
                with col_bm:
                    if st.button("⭐ 要復習リストに保存", key=f"btn_bm_{idx}"):
                        with get_db() as conn:
                            cur = conn.cursor()
                            cur.execute("""
                            INSERT OR IGNORE INTO quiz_bookmarks (user_id, question_id, term_name)
                            VALUES (?, ?, ?)
                            """, (st.session_state.user_id, q_id, q_term))
                            conn.commit()
                        st.toast(f"「{q_term}」を要復習リストに追加しました！")

                # イラストの表示
                with get_db() as conn_img:
                    c_img = conn_img.cursor()
                    c_img.execute("SELECT image_path FROM terms WHERE term_name = ?", (q_term,))
                    r_img = c_img.fetchone()
                    q_img_path = r_img[0] if r_img else None

                if q_img_path and os.path.exists(q_img_path):
                    with st.expander("🎨 概念イメージイラストを見る", expanded=True):
                        st.image(q_img_path, caption=f"{q_term} の図解・解法ステップ", use_container_width=True)

                st.markdown("---")
                st.subheader("💡 学習者属性別 詳細解説")
                
                if st.session_state.major_type == "情報科学科・理系":
                    tab_main, tab_sub = st.tabs(["🔬 情報科学科向け技術解説（主解説）", "🌱 初学者・文系向け解説"])
                    with tab_main:
                        render_two_tier_explanation(exp_adv, "情報科学科向け技術解説")
                    with tab_sub:
                        render_two_tier_explanation(exp_beg, "初学者・文系向け解説")
                else:
                    tab_main, tab_sub = st.tabs(["🌱 初学者・文系向け解説（主解説）", "🔬 情報科学科向け技術解説"])
                    with tab_main:
                        render_two_tier_explanation(exp_beg, "初学者・文系向け解説")
                    with tab_sub:
                        render_two_tier_explanation(exp_adv, "情報科学科向け技術解説")

                c_next, c_abort = st.columns([1, 1])
                with c_next:
                    btn_text = "次の問題へ ➔" if (idx + 1) < total else "演習結果を確認する 🏆"
                    if st.button(btn_text, type="primary", key=f"btn_next_{idx}"):
                        st.session_state.quiz_index += 1
                        st.session_state.quiz_answered_current = False
                        st.session_state.q_start_time = time.time()
                        st.rerun()
                with c_abort:
                    if st.button("演習を中断して設定に戻る", key=f"btn_abort_{idx}"):
                        st.session_state.quiz_active = False
                        st.rerun()

# ---------------------------------------------------------
# メイン画面：弱点復習リスト（復習特訓）
# ---------------------------------------------------------
elif st.session_state.app_mode == "弱点復習リスト":
    st.markdown('<h1 translate="no">⭐ 要復習ブックマークリスト</h1>', unsafe_allow_html=True)
    st.caption("演習中に保存した「苦手な問題」をピンポイントで復習・再学習できます。")

    with get_db() as conn:
        df_bm = pd.read_sql_query("""
        SELECT b.id as bm_id, b.question_id, b.term_name, b.created_at,
               q.question_text, q.correct_ans, qeb.explanation as exp_beg, qea.explanation as exp_adv
        FROM quiz_bookmarks b
        JOIN questions q ON b.question_id = q.id
        LEFT JOIN question_explanations_beginner qeb ON q.id = qeb.question_id
        LEFT JOIN question_explanations_advanced qea ON q.id = qea.question_id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
        """, conn, params=(st.session_state.user_id,))

    if df_bm.empty:
        st.info("現在保存されている要復習問題はありません。問題演習の解説画面から「⭐ 要復習リストに保存」を押して登録してください。")
    else:
        st.write(f"登録済みの弱点問題： **{len(df_bm)}** 件")
        for _, row in df_bm.iterrows():
            with st.expander(f"📌 {row['term_name']} （登録日時: {row['created_at']}）"):
                st.write(f"**問題：** {row['question_text']}")
                st.write(f"**正解記号：** {row['correct_ans']}")
                
                t1, t2 = st.tabs(["🌱 文系・初学者向け解説", "🔬 情報系向け詳細技術解説"])
                with t1:
                    render_two_tier_explanation(row['exp_beg'], "文系・初学者")
                with t2:
                    render_two_tier_explanation(row['exp_adv'], "情報系向け")
                
                if st.button("🗑️ 復習完了（リストから削除）", key=f"del_bm_{row['bm_id']}"):
                    with get_db() as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM quiz_bookmarks WHERE id = ?", (row['bm_id'],))
                        conn.commit()
                    st.rerun()
