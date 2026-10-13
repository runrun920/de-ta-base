import streamlit as st
import sqlite3
import random
import os
import logging
import pandas as pd

# ---------------------------------------------------------
# 1. 基本設定・UI統一設定
# ---------------------------------------------------------
st.set_page_config(page_title="FE-AI Tutor | 事前・事後テスト", page_icon="📝", layout="wide")

st.markdown("""
<meta name="google" content="notranslate">
<style>
    html, body, [class*="css"], .stApp {
        translate: no !important;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "fe_study.db"
LOG_FILE = "test_app.log"

def setup_logger():
    logger = logging.getLogger("FE_TEST_LOGGER")
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
    st.stop()

# ---------------------------------------------------------
# 2. テスト用テーブルの初期化
# ---------------------------------------------------------
def init_test_db():
    conn = get_db()
    cur = conn.cursor()
    # テストの成績・ログテーブル
    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        test_type TEXT, -- '事前テスト' または '事後テスト'
        question_id INTEGER,
        term_name TEXT,
        sub_category TEXT,
        selected_choice TEXT,
        correct_ans TEXT,
        is_correct INTEGER,
        answered_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # テスト全体の完了サマリー
    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        test_type TEXT,
        score INTEGER,
        total_questions INTEGER,
        accuracy_rate REAL,
        completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, test_type)
    )
    """)
    conn.commit()
    conn.close()

init_test_db()

# ---------------------------------------------------------
# 3. セッション状態の初期化
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_name = ""
    st.session_state.major_type = "文系・初学者"

if "test_mode" not in st.session_state:
    st.session_state.test_mode = "HOME" # HOME, PRE_TEST, POST_TEST, RESULT

if "test_questions" not in st.session_state:
    st.session_state.test_questions = []
if "test_index" not in st.session_state:
    st.session_state.test_index = 0
if "test_user_answers" not in st.session_state:
    st.session_state.test_user_answers = {}
if "current_test_type" not in st.session_state:
    st.session_state.current_test_type = ""

# ---------------------------------------------------------
# 4. ログイン画面（既存システムと完全統一）
# ---------------------------------------------------------
if not st.session_state.logged_in:
    st.markdown('<h1 translate="no">📝 基本情報技術者試験 効果検証システム</h1>', unsafe_allow_html=True)
    st.subheader("被験者ログイン")
    
    col1, _ = st.columns([1.2, 1])
    with col1:
        input_uid = st.text_input("学籍番号 または 被験者ID：", placeholder="例: G23937")
        input_name = st.text_input("お名前：", placeholder="例: 奥田 さえ")
        input_major = st.radio("専攻・バックグラウンドを選択：", ["文系・初学者", "情報科学科・理系"], horizontal=True)
        
        if st.button("ログインして評価テストに進む", type="primary"):
            if input_uid.strip() and input_name.strip():
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    user_name TEXT,
                    last_login DATETIME
                )
                """)
                cur.execute("""
                INSERT INTO users (user_id, user_name, last_login) VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET last_login=CURRENT_TIMESTAMP, user_name=?
                """, (input_uid.strip(), input_name.strip(), input_name.strip()))
                conn.commit()
                conn.close()
                
                st.session_state.logged_in = True
                st.session_state.user_id = input_uid.strip()
                st.session_state.user_name = input_name.strip()
                st.session_state.major_type = input_major
                
                logger.info(f"TEST_USER_LOGIN: user_id={input_uid.strip()}, major={input_major}")
                st.rerun()
            else:
                st.error("学籍番号とお名前を入力してください。")
    st.stop()

# ---------------------------------------------------------
# 5. サイドバー
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div translate="no">👤 被験者: <b>{st.session_state.user_name}</b> さん<br><small>ID: {st.session_state.user_id} ｜ {st.session_state.major_type}</small></div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # テスト受験状況の確認
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT test_type, score, total_questions FROM test_results WHERE user_id = ?", (st.session_state.user_id,))
    completed_tests = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    conn.close()

    st.subheader("📊 受験ステータス")
    pre_status = f"✅ 完了 ({completed_tests['事前テスト'][0]}/{completed_tests['事前テスト'][1]})" if "事前テスト" in completed_tests else "❌ 未受験"
    post_status = f"✅ 完了 ({completed_tests['事後テスト'][0]}/{completed_tests['事後テスト'][1]})" if "事後テスト" in completed_tests else "❌ 未受験"
    
    st.write(f"・事前テスト: {pre_status}")
    st.write(f"・事後テスト: {post_status}")

    st.markdown("---")
    if st.button("ログアウト", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.test_mode = "HOME"
        st.rerun()

# ---------------------------------------------------------
# 6. 出題ロジック（事前・事後で難易度/中分類を完全に同一化）
# ---------------------------------------------------------
TARGET_SUB_CATEGORIES = [
    "セキュリティ", "基礎理論", "コンピュータ構成要素", 
    "データベース", "ネットワーク", "ソフトウェア",
    "プロジェクトマネジメント", "サービスマネジメント",
    "企業活動", "経営戦略マネジメント"
]

def generate_test_questions(test_type):
    """
    指定した中分類からそれぞれ問題を1問ずつ抽出し、10問のセットを作成する。
    事前・事後で同じ問題が重複しないようにランダムシードまたは除外処理を行う。
    """
    conn = get_db()
    cur = conn.cursor()
    
    questions = []
    
    # 事前テストで解答済みの問題IDを取得（事後テストで重複させないため）
    used_q_ids = []
    if test_type == "事後テスト":
        cur.execute("SELECT question_id FROM test_logs WHERE user_id = ? AND test_type = '事前テスト'", (st.session_state.user_id,))
        used_q_ids = [r[0] for r in cur.fetchall()]

    for sub_cat in TARGET_SUB_CATEGORIES:
        if used_q_ids:
            placeholders = ','.join('?' for _ in used_q_ids)
            query = f"""
            SELECT id, term_name, sub_category, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, explanation_beginner
            FROM terms_master
            WHERE sub_category LIKE ? AND question_text IS NOT NULL AND question_text != ''
            AND id NOT IN ({placeholders})
            """
            cur.execute(query, [f"%{sub_cat}%"] + used_q_ids)
        else:
            query = """
            SELECT id, term_name, sub_category, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, explanation_beginner
            FROM terms_master
            WHERE sub_category LIKE ? AND question_text IS NOT NULL AND question_text != ''
            """
            cur.execute(query, [f"%{sub_cat}%"])
        
        rows = cur.fetchall()
        if rows:
            questions.append(random.choice(rows))
        else:
            # 万が一該当中分類に未出題問題がない場合は全問からフォールバック
            cur.execute("SELECT id, term_name, sub_category, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, explanation_beginner FROM terms_master WHERE question_text IS NOT NULL AND question_text != ''")
            questions.append(random.choice(cur.fetchall()))
            
    conn.close()
    return questions

# ---------------------------------------------------------
# 7. メイン画面の挙動制御
# ---------------------------------------------------------

# 【ホーム画面】
if st.session_state.test_mode == "HOME":
    st.title("📝 効果測定システム（事前・事後テスト）")
    st.write("学習システムの利用効果を検証するため、学習前と学習後にそれぞれ10問のテストを行います。")
    st.info("※ 事前テストと事後テストは、出題される分野（難易度）が同一となるよう設計されています。")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. 事前テスト")
        st.write("学習システムを利用する前に受験してください。")
        if "事前テスト" in completed_tests:
            st.success(f"受講済み（スコア: {completed_tests['事前テスト'][0]} / {completed_tests['事前テスト'][1]}）")
            if st.button("事前テスト結果を再確認する"):
                st.session_state.current_test_type = "事前テスト"
                st.session_state.test_mode = "RESULT_VIEW"
                st.rerun()
        else:
            if st.button("🚀 事前テストを開始する", type="primary", use_container_width=True):
                st.session_state.test_questions = generate_test_questions("事前テスト")
                st.session_state.test_index = 0
                st.session_state.test_user_answers = {}
                st.session_state.current_test_type = "事前テスト"
                st.session_state.test_mode = "TEST_RUN"
                logger.info(f"PRE_TEST_START: user_id={st.session_state.user_id}")
                st.rerun()

    with col2:
        st.subheader("2. 事後テスト")
        st.write("学習システムでの学習を終えた後に受験してください。")
        if "事後テスト" in completed_tests:
            st.success(f"受講済み（スコア: {completed_tests['事後テスト'][0]} / {completed_tests['事後テスト'][1]}）")
            if st.button("事後テスト結果を再確認する"):
                st.session_state.current_test_type = "事後テスト"
                st.session_state.test_mode = "RESULT_VIEW"
                st.rerun()
        else:
            can_start = "事前テスト" in completed_tests
            if st.button("🚀 事後テストを開始する", type="primary", use_container_width=True, disabled=not can_start):
                st.session_state.test_questions = generate_test_questions("事後テスト")
                st.session_state.test_index = 0
                st.session_state.test_user_answers = {}
                st.session_state.current_test_type = "事後テスト"
                st.session_state.test_mode = "TEST_RUN"
                logger.info(f"POST_TEST_START: user_id={st.session_state.user_id}")
                st.rerun()
            if not can_start:
                st.caption("⚠️ 事前テスト完了後に開放されます。")

# 【テスト解答画面】
elif st.session_state.test_mode == "TEST_RUN":
    q_list = st.session_state.test_questions
    idx = st.session_state.test_index
    total = len(q_list)
    test_type = st.session_state.current_test_type

    st.markdown(f"## 📝 {test_type} （{idx + 1} / {total} 問）")
    
    if idx < total:
        q = q_list[idx]
        q_id, q_term, q_sub_cat, q_text, c_a, c_b, c_c, c_d, c_ans, exp = q

        st.progress((idx + 1) / total)
        st.caption(f"出題分野（中分類）: **{q_sub_cat}** ｜ 対象用語: {q_term}")
        
        st.markdown(f"### Q{idx + 1}. {q_text}")

        choices = [f"ア: {c_a}", f"イ: {c_b}", f"ウ: {c_c}", f"エ: {c_d}"]
        
        # すでに回答済みか判定
        already_selected = st.session_state.test_user_answers.get(idx, {}).get("selected_choice", None)
        default_index = [c[0] for c in choices].index(already_selected) if already_selected else 0

        user_choice = st.radio("選択肢：", choices, index=default_index, key=f"test_radio_{idx}")
        selected_char = user_choice[0]

        col_prev, col_next = st.columns([1, 1])
        
        with col_prev:
            if idx > 0:
                if st.button("⬅️ 前の問題へ"):
                    st.session_state.test_user_answers[idx] = {
                        "q_id": q_id, "term": q_term, "sub_cat": q_sub_cat,
                        "selected_choice": selected_char, "correct_ans": c_ans
                    }
                    st.session_state.test_index -= 1
                    st.rerun()

        with col_next:
            btn_label = "次の問題へ ➔" if (idx + 1) < total else "テストを提出する 🏁"
            if st.button(btn_label, type="primary"):
                # 解答を記録
                st.session_state.test_user_answers[idx] = {
                    "q_id": q_id, "term": q_term, "sub_cat": q_sub_cat,
                    "selected_choice": selected_char, "correct_ans": c_ans
                }
                
                if (idx + 1) < total:
                    st.session_state.test_index += 1
                    st.rerun()
                else:
                    # 全問回答完了 -> DBへ保存処理
                    conn = get_db()
                    cur = conn.cursor()
                    correct_count = 0
                    
                    for i, a_data in st.session_state.test_user_answers.items():
                        is_corr = 1 if a_data["selected_choice"] == a_data["correct_ans"].strip() else 0
                        if is_corr:
                            correct_count += 1
                            
                        cur.execute("""
                        INSERT INTO test_logs (user_id, test_type, question_id, term_name, sub_category, selected_choice, correct_ans, is_correct)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, test_type, a_data["q_id"], a_data["term"], a_data["sub_cat"], a_data["selected_choice"], a_data["correct_ans"], is_corr))
                    
                    acc_rate = (correct_count / total) * 100
                    cur.execute("""
                    INSERT INTO test_results (user_id, test_type, score, total_questions, accuracy_rate)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, test_type) DO UPDATE SET score=?, accuracy_rate=?, completed_at=CURRENT_TIMESTAMP
                    """, (st.session_state.user_id, test_type, correct_count, total, acc_rate, correct_count, acc_rate))
                    
                    conn.commit()
                    conn.close()
                    
                    logger.info(f"TEST_COMPLETED: user={st.session_state.user_id}, type={test_type}, score={correct_count}/{total}")
                    st.session_state.test_mode = "RESULT_VIEW"
                    st.rerun()

# 【結果表示画面】
elif st.session_state.test_mode == "RESULT_VIEW":
    test_type = st.session_state.current_test_type
    st.title(f"🏆 {test_type} 結果")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT score, total_questions, accuracy_rate FROM test_results WHERE user_id = ? AND test_type = ?", (st.session_state.user_id, test_type))
    res = cur.fetchone()
    
    if res:
        score, total, rate = res
        st.metric("正解数 / 出題数", f"{score} / {total} 問", f"正答率 {rate:.1f}%")
        
        st.markdown("---")
        st.subheader("📋 出題分野別の正誤分析")
        
        df_logs = pd.read_sql("""
        SELECT sub_category AS 分野, term_name AS 対象用語, selected_choice AS あなたの回答, correct_ans AS 正解,
               CASE WHEN is_correct = 1 THEN '✅ 正解' ELSE '❌ 不正解' END AS 判定
        FROM test_logs
        WHERE user_id = ? AND test_type = ?
        """, conn, params=(st.session_state.user_id, test_type))
        
        st.dataframe(df_logs, use_container_width=True)

    conn.close()

    if st.button("🏠 ホームへ戻る", type="primary"):
        st.session_state.test_mode = "HOME"
        st.rerun()