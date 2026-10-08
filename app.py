import streamlit as st
import sqlite3
import random
import os
import logging

st.set_page_config(page_title="FE-AI Tutor", page_icon="🎓", layout="wide")

st.markdown("""
<meta name="google" content="notranslate">
<style>
    html, body, [class*="css"], .stApp {
        translate: no !important;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "fe_study.db"
LOG_FILE = "app.log"

def setup_logger():
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

# セッション状態の初期化
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_name = ""
    st.session_state.major_type = "文系・初学者"
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "ホーム"
if "current_term" not in st.session_state:
    st.session_state.current_term = "機密性"
if "quiz_active" not in st.session_state:
    st.session_state.quiz_active = False
if "quiz_questions" not in st.session_state:
    st.session_state.quiz_questions = []
if "quiz_index" not in st.session_state:
    st.session_state.quiz_index = 0
if "quiz_user_answers" not in st.session_state:
    st.session_state.quiz_user_answers = {}
if "quiz_answered_current" not in st.session_state:
    st.session_state.quiz_answered_current = False

# ログイン画面
if not st.session_state.logged_in:
    st.markdown('<h1 translate="no">🎓 基本情報技術者試験 学習支援システム (FE-AI Tutor)</h1>', unsafe_allow_html=True)
    st.subheader("ログイン")
    
    col1, _ = st.columns([1.2, 1])
    with col1:
        input_uid = st.text_input("学籍番号 または ユーザーID：", placeholder="例: G23937")
        input_name = st.text_input("お名前：", placeholder="例: 奥田 さえ")
        input_major = st.radio("専攻・バックグラウンドを選択：", ["文系・初学者", "情報科学科・理系"], horizontal=True)
        
        if st.button("ログインして始める", type="primary"):
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
                
                logger.info(f"USER_LOGIN: user_id={input_uid.strip()}, major={input_major}")
                st.rerun()
            else:
                st.error("学籍番号とお名前を入力してください。")
    st.stop()

# サイドバー
with st.sidebar:
    st.markdown(f'<div translate="no">👤 ログイン中: <b>{st.session_state.user_name}</b> さん<br><small>ID: {st.session_state.user_id} ｜ {st.session_state.major_type}</small></div>', unsafe_allow_html=True)
    st.markdown("---")

    menu_options = ["🏠 ホーム", "📖 用語を勉強する", "📝 問題を解く"]
    current_index = 0
    if st.session_state.app_mode == "用語を勉強する":
        current_index = 1
    elif st.session_state.app_mode == "問題を解く":
        current_index = 2

    selected_menu = st.radio("メニュー切替：", menu_options, index=current_index)
    if selected_menu == "🏠 ホーム":
        st.session_state.app_mode = "ホーム"
    elif selected_menu == "📖 用語を勉強する":
        st.session_state.app_mode = "用語を勉強する"
    elif selected_menu == "📝 問題を解く":
        st.session_state.app_mode = "問題を解く"

    if st.session_state.app_mode == "用語を勉強する":
        st.markdown("---")
        st.subheader("🔍 用語を探す")
        search_mode = st.radio("検索方法：", ["キーワードから探す", "分野から絞り込む"])
        
        conn = get_db()
        cur = conn.cursor()

        if search_mode == "キーワードから探す":
            try:
                cur.execute("SELECT term_name FROM terms_master ORDER BY id")
                master_terms = [r[0] for r in cur.fetchall()]
            except Exception:
                master_terms = []

            try:
                cur.execute("SELECT DISTINCT term_name FROM terms ORDER BY term_name")
                all_terms_list = [r[0] for r in cur.fetchall()]
            except Exception:
                all_terms_list = []

            ordered_terms = master_terms + [t for t in all_terms_list if t not in master_terms]
            if not ordered_terms:
                ordered_terms = ["機密性", "完全性", "可用性"]

            kw = st.text_input("検索キーワード：", placeholder="例: 機密性, RAID")
            matched = [t for t in ordered_terms if kw.strip().lower() in t.lower()] if kw.strip() else ordered_terms

            if matched:
                def_idx = matched.index(st.session_state.current_term) if st.session_state.current_term in matched else 0
                st.session_state.current_term = st.selectbox(f"該当用語（{len(matched)}件）：", options=matched, index=def_idx)
            else:
                st.warning("一致する用語がありません。")

        elif search_mode == "分野から絞り込む":
            c_sel = st.selectbox("1. 大分類：", list(SYLLABUS_STRUCTURE.keys()))
            s_sel = st.selectbox("2. 中分類：", SYLLABUS_STRUCTURE[c_sel])

            try:
                cur.execute("SELECT term_name FROM terms_master WHERE sub_category = ?", (s_sel,))
                m_terms = [r[0] for r in cur.fetchall()]
            except Exception:
                m_terms = []

            try:
                cur.execute("SELECT DISTINCT term_name FROM term_categories WHERE sub_category = ? ORDER BY term_name", (s_sel,))
                t_terms = [r[0] for r in cur.fetchall()]
            except Exception:
                cur.execute("SELECT DISTINCT term_name FROM terms WHERE sub_category = ? ORDER BY term_name", (s_sel,))
                t_terms = [r[0] for r in cur.fetchall()]

            f_terms = m_terms + [t for t in t_terms if t not in m_terms]
            if f_terms:
                def_idx = f_terms.index(st.session_state.current_term) if st.session_state.current_term in f_terms else 0
                st.session_state.current_term = st.selectbox(f"3. 対象用語（{len(f_terms)}件）：", options=f_terms, index=def_idx)
            else:
                st.info(f"「{s_sel}」の登録用語は現在0件です。")

        conn.close()
    
    st.markdown("---")
    col_out, col_del = st.columns(2)
    with col_out:
        if st.button("ログアウト", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.app_mode = "ホーム"
            st.session_state.quiz_active = False
            st.rerun()

    with col_del:
        with st.popover("退会・削除", use_container_width=True):
            st.warning("アカウントとこれまでの学習履歴がすべて削除されます。")
            if st.button("本当に削除する", type="primary", key="btn_self_delete"):
                conn = get_db()
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE user_id = ?", (st.session_state.user_id,))
                cur.execute("DELETE FROM quiz_logs WHERE user_id = ?", (st.session_state.user_id,))
                cur.execute("DELETE FROM term_logs WHERE user_id = ?", (st.session_state.user_id,))
                cur.execute("DELETE FROM content_view_logs WHERE user_id = ?", (st.session_state.user_id,))
                conn.commit()
                conn.close()

                logger.info(f"USER_DELETED: user_id={st.session_state.user_id}")
                st.session_state.logged_in = False
                st.session_state.app_mode = "ホーム"
                st.session_state.quiz_active = False
                st.rerun()

# メイン画面の分岐
if st.session_state.app_mode == "ホーム":
    st.markdown(f'<h1 translate="no">ようこそ、{st.session_state.user_name} さん！ 👋</h1>', unsafe_allow_html=True)
    st.write("基本情報技術者試験（科目A）の対策を始めましょう。学習目的を選択してください。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📖 用語を勉強する\nシラバス全23分類の辞書に加え、「直感的な例え話」「身近な実用例」「公式定義」の3層で解説をしています。")
        if st.button("用語学習へ進む ➔", key="btn_go_study", type="primary"):
            st.session_state.app_mode = "用語を勉強する"
            st.rerun()
            
    with col2:
        st.success("### 📝 問題を解く\nデータベースに収録された予想問題に挑戦。文系・情報科学科それぞれの属性に最適化された解説付き。")
        if st.button("問題演習へ進む ➔", key="btn_go_quiz", type="primary"):
            st.session_state.app_mode = "問題を解く"
            st.rerun()

elif st.session_state.app_mode == "用語を勉強する":
    curr = st.session_state.current_term
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS content_view_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        term_name TEXT,
        content_type TEXT,
        viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 用語基本情報（terms）の取得
    cur.execute("SELECT id, category, sub_category, official_def, url FROM terms WHERE term_name = ?", (curr,))
    term_row = cur.fetchone()
    
    term_id = term_row[0] if term_row else None
    cat = term_row[1] if term_row else "テクノロジ系"
    sub_cat = term_row[2] if term_row else "未分類"
    off_def = term_row[3] if term_row else ""
    url = term_row[4] if term_row else ""

    # 比喩テーブル（term_metaphors）から取得
    int_def = ""
    if term_id:
        cur.execute("SELECT metaphor_text FROM term_metaphors WHERE term_id = ? AND source_ai = 'Final'", (term_id,))
        m_row = cur.fetchone()
        if m_row:
            int_def = m_row[0]

    # 実用例テーブル（term_examples）から取得
    prac_ex = ""
    if term_id:
        cur.execute("SELECT example_text FROM term_examples WHERE term_id = ? AND source_ai = 'Final'", (term_id,))
        e_row = cur.fetchone()
        if e_row:
            prac_ex = e_row[0]

    # 全体閲覧ログ (term_logs) の記録
    try:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS term_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            term_name TEXT,
            category TEXT,
            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("INSERT INTO term_logs (user_id, term_name, category) VALUES (?, ?, ?)",
                    (st.session_state.user_id, curr, cat))
        conn.commit()
    except Exception:
        pass

    # 画面描画
    has_custom = bool(int_def or prac_ex)
    badge = "（★特製コンテンツ完備）" if has_custom else ""
    st.caption(f"📚 {cat} ＞ {sub_cat} {badge}")
    st.markdown(f'<h1 translate="no">💻 {curr}</h1>', unsafe_allow_html=True)

    # 全用語共通で3つの解説タイプを選択できるように統一
    view_choice = st.radio(
        "解説の種類を選択してください（閲覧ログが研究データとして記録されます）：",
        ["💡 直感理解（例え話）", "🌍 身近な実用例", "📖 試験対策（公式定義）"],
        horizontal=True,
        key=f"view_choice_{curr}"
    )

    content_type_map = {
        "💡 直感理解（例え話）": "metaphor",
        "🌍 身近な実用例": "example",
        "📖 試験対策（公式定義）": "official"
    }
    selected_type = content_type_map[view_choice]

    try:
        cur.execute("""
        INSERT INTO content_view_logs (user_id, term_name, content_type)
        VALUES (?, ?, ?)
        """, (st.session_state.user_id, curr, selected_type))
        conn.commit()
        logger.info(f"CONTENT_VIEW: user={st.session_state.user_id}, term={curr}, type={selected_type}")
    except Exception as e:
        logger.error(f"LOG_ERROR: {e}")

    # コンテンツの表示（データがない用語は丁寧な準備中案内を表示）
    if view_choice == "💡 直感理解（例え話）":
        if int_def and int_def.strip():
            st.info(int_def)
        else:
            st.info("💡 **直感理解（例え話）**\n\n※この用語の直感的な比喩解説は現在準備中です。")

    elif view_choice == "🌍 身近な実用例":
        if prac_ex and prac_ex.strip():
            st.success(prac_ex)
        else:
            st.success("🌍 **身近な実用例**\n\n※この用語の身近な実用例は現在準備中です。")

    elif view_choice == "📖 試験対策（公式定義）":
        if off_def and off_def.strip():
            st.warning(off_def)
        else:
            st.warning("📖 **公式定義**\n\n※公式定義データ準備中")
        if url and url.strip():
            st.caption(f"[過去問道場で確認する]({url})")

    conn.close()

elif st.session_state.app_mode == "問題を解く":
    st.markdown('<h1 translate="no">📝 実戦問題演習モード（科目A試験対策）</h1>', unsafe_allow_html=True)

    if not st.session_state.quiz_active:
        st.subheader("演習設定")
        st.caption("データベース（`terms_master`）に収録された問題から出題されます。")

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM terms_master WHERE question_text IS NOT NULL AND question_text != ''")
            avail_q_count = cur.fetchone()[0]
        except Exception:
            avail_q_count = 0
        conn.close()

        if avail_q_count == 0:
            st.warning("現在出題可能な問題がありません。先に `python3 sync_db.py` を実行してください。")
            st.stop()

        max_options = [cnt for cnt in [5, 10, 15, 30] if cnt < avail_q_count] + [avail_q_count]
        num_choice = st.radio("出題数：", max_options, format_func=lambda x: f"{x}問 （登録全問演習）" if x == avail_q_count else f"{x}問", horizontal=True)

        if st.button("🚀 演習を開始する", type="primary"):
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
            SELECT id, term_name, question_text, choice_a, choice_b, choice_c, choice_d, 
                   correct_ans, explanation_beginner, explanation_advanced 
            FROM terms_master 
            WHERE question_text IS NOT NULL AND question_text != ''
            """)
            q_rows = cur.fetchall()
            conn.close()

            random.shuffle(q_rows)
            st.session_state.quiz_questions = q_rows[:num_choice]
            st.session_state.quiz_index = 0
            st.session_state.quiz_user_answers = {}
            st.session_state.quiz_answered_current = False
            st.session_state.quiz_active = True
            logger.info(f"QUIZ_START: user_id={st.session_state.user_id}, total={num_choice}")
            st.rerun()

    else:
        q_list = st.session_state.quiz_questions
        idx = st.session_state.quiz_index
        total = len(q_list)

        if idx >= total:
            st.success("🎉 全問解答完了！")
            correct_count = sum(1 for a in st.session_state.quiz_user_answers.values() if a["is_correct"])
            rate = (correct_count / total) * 100
            st.metric("正答率", f"{rate:.1f}%", f"{correct_count} / {total} 問正解")

            if rate >= 60.0:
                st.balloons()
                st.success("🏆 合格基準点（60%）達成！")
            else:
                st.info("💡 基準点は60%です。解説を復習して再挑戦しましょう。")

            st.markdown("---")
            st.subheader("📋 解答一覧と詳細解説")
            for i, q in enumerate(q_list):
                q_id, q_term, q_text, c_a, c_b, c_c, c_d, c_ans, exp_beg, exp_adv = q
                ans_data = st.session_state.quiz_user_answers.get(i, {})
                with st.expander(f"問 {i+1}：{q_term} — {'✅ 正解' if ans_data.get('is_correct') else '❌ 不正解'}"):
                    st.write(f"**問題：** {q_text}")
                    st.write(f"**あなたの回答：** {ans_data.get('selected')} ｜ **正解：** {c_ans}")
                    
                    sub_t1, sub_t2 = st.tabs(["🌱 文系・初学者向け解説", "🔬 情報科学科向け解説"])
                    with sub_t1:
                        st.info(exp_beg if exp_beg else "※解説準備中")
                    with sub_t2:
                        st.info(exp_adv if exp_adv else "※解説準備中")

            if st.button("🔄 もう一度演習する", type="primary"):
                st.session_state.quiz_active = False
                st.rerun()

        else:
            q = q_list[idx]
            q_id, q_term, q_text, c_a, c_b, c_c, c_d, c_ans, exp_beg, exp_adv = q

            st.progress((idx + 1) / total)
            st.caption(f"問題 {idx + 1} / {total} ｜ 対象用語：{q_term}")
            st.markdown(f'<h3 translate="no">Q{idx + 1}. {q_text}</h3>', unsafe_allow_html=True)

            choices = [f"ア: {c_a}", f"イ: {c_b}", f"ウ: {c_c}", f"エ: {c_d}"]
            user_choice = st.radio("選択肢：", choices, key=f"q_radio_{idx}", disabled=st.session_state.quiz_answered_current)
            selected_char = user_choice[0]

            if not st.session_state.quiz_answered_current:
                if st.button("回答を送信する", type="primary"):
                    is_correct = (selected_char == c_ans.strip())
                    st.session_state.quiz_user_answers[idx] = {
                        "question_id": q_id,
                        "selected": selected_char,
                        "is_correct": is_correct
                    }
                    st.session_state.quiz_answered_current = True

                    try:
                        conn = get_db()
                        cur = conn.cursor()
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
                        cur.execute("""
                        INSERT INTO quiz_logs (user_id, question_id, term_name, selected_choice, is_correct)
                        VALUES (?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, q_id, q_term, selected_char, 1 if is_correct else 0))
                        conn.commit()
                        conn.close()
                        logger.info(f"QUIZ_ANSWER: user={st.session_state.user_id}, term={q_term}, ans={selected_char}, correct={is_correct}")
                    except Exception as e:
                        logger.error(f"LOG_ERROR: {e}")

                    st.rerun()

            else:
                ans_data = st.session_state.quiz_user_answers[idx]
                if ans_data["is_correct"]:
                    st.success(f"🎉 正解です！（正解：{c_ans}）")
                else:
                    st.error(f"❌ 不正解です... あなたの回答：{ans_data['selected']}（正解：{c_ans}）")

                st.markdown("---")
                st.subheader("💡 学習者属性別 詳細解説")
                if st.session_state.major_type == "情報科学科・理系":
                    tab_main, tab_sub = st.tabs(["🔬 情報科学科（上級）向け解説", "🌱 IT初心者・文系向け解説"])
                    with tab_main:
                        st.info(exp_adv if exp_adv else "※解説準備中")
                    with tab_sub:
                        st.info(exp_beg if exp_beg else "※解説準備中")
                else:
                    tab_main, tab_sub = st.tabs(["🌱 IT初心者・文系向け解説", "🔬 情報科学科（上級）向け解説"])
                    with tab_main:
                        st.info(exp_beg if exp_beg else "※解説準備中")
                    with tab_sub:
                        st.info(exp_adv if exp_adv else "※解説準備中")

                col_next, col_abort = st.columns([1, 1])
                with col_next:
                    btn_text = "次の問題へ ➔" if (idx + 1) < total else "結果を確認する 🏆"
                    if st.button(btn_text, type="primary"):
                        st.session_state.quiz_index += 1
                        st.session_state.quiz_answered_current = False
                        st.rerun()
                with col_abort:
                    if st.button("演習を中断して戻る"):
                        st.session_state.quiz_active = False
                        st.rerun()