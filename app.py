import streamlit as st
import sqlite3
import random
import datetime

# ページ設定
st.set_page_config(page_title="FE-AI Tutor", page_icon="🎓", layout="wide")

# 翻訳ツールの暴走・フリーズ防止メタ設定
st.markdown("""
<meta name="google" content="notranslate">
<style>
    .notranslate { translate: no !important; }
</style>
""", unsafe_allow_html=True)

def get_db():
    return sqlite3.connect("fe_study.db")

# ==========================================
# 0. IPA公式シラバス階層マスター（全3大分類・全23中分類）
# ==========================================
SYLLABUS_STRUCTURE = {
    "テクノロジ系": [
        "1. 基礎理論",
        "2. アルゴリズムとプログラミング",
        "3. コンピュータ構成要素",
        "4. システム構成要素",
        "5. ソフトウェア",
        "6. ハードウェア",
        "7. ユーザーインタフェース",
        "8. 情報メディア",
        "9. データベース",
        "10. ネットワーク",
        "11. セキュリティ",
        "12. システム開発技術",
        "13. ソフトウェア開発管理技術"
    ],
    "マネジメント系": [
        "14. プロジェクトマネジメント",
        "15. サービスマネジメント",
        "16. システム監査"
    ],
    "ストラテジ系": [
        "17. システム戦略",
        "18. システム企画",
        "19. 経営戦略マネジメント",
        "20. 技術戦略マネジメント",
        "21. ビジネスインダストリ",
        "22. 企業活動",
        "23. 法務"
    ]
}

# ==========================================
# 1. セッション状態の初期化
# ==========================================
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

# ==========================================
# 2. ログイン画面
# ==========================================
if not st.session_state.logged_in:
    st.markdown('<h1 class="notranslate" translate="no">🎓 基本情報技術者試験 学習支援システム (FE-AI Tutor)</h1>', unsafe_allow_html=True)
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
                st.rerun()
            else:
                st.error("学籍番号とお名前を入力してください。")
    st.stop()

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.markdown(f'<div class="notranslate" translate="no">👤 ログイン中: <b>{st.session_state.user_name}</b> さん<br><small>ID: {st.session_state.user_id} ｜ {st.session_state.major_type}</small></div>', unsafe_allow_html=True)
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

    # 用語学習モード用検索
    if st.session_state.app_mode == "用語を勉強する":
        st.markdown("---")
        st.subheader("🔍 用語を探す")
        
        search_mode = st.radio("検索方法：", ["キーワードから探す", "分野から絞り込む"])
        
        conn = get_db()
        cur = conn.cursor()

        if search_mode == "キーワードから探す":
            # terms_master の重要語
            try:
                cur.execute("SELECT term_name FROM terms_master ORDER BY id")
                master_terms = [r[0] for r in cur.fetchall()]
            except Exception:
                master_terms = []

            # terms（全3,300語）
            try:
                cur.execute("SELECT DISTINCT term_name FROM terms ORDER BY term_name")
                all_terms_list = [r[0] for r in cur.fetchall()]
            except Exception:
                all_terms_list = []

            ordered_terms = master_terms + [t for t in all_terms_list if t not in master_terms]
            if not ordered_terms:
                ordered_terms = ["機密性", "完全性", "可用性"]

            kw = st.text_input("検索キーワード：", placeholder="例: 機密性, RAID", key="kw_search_box")
            if kw.strip():
                matched = [t for t in ordered_terms if kw.strip().lower() in t.lower()]
            else:
                matched = ordered_terms

            if matched:
                def_idx = matched.index(st.session_state.current_term) if st.session_state.current_term in matched else 0
                chosen = st.selectbox(f"該当用語（{len(matched)}件）：", options=matched, index=def_idx)
                st.session_state.current_term = chosen
            else:
                st.warning("一致する用語がありません。")

        elif search_mode == "分野から絞り込む":
            # 1. 大分類
            cat_options = list(SYLLABUS_STRUCTURE.keys())
            c_sel = st.selectbox("1. 大分類：", cat_options)

            # 2. 中分類
            sub_options = SYLLABUS_STRUCTURE[c_sel]
            s_sel = st.selectbox("2. 中分類：", sub_options)

            # 3. term_categories テーブル（正確なマッピング）から取得
            # terms_master の優先用語
            try:
                cur.execute("SELECT term_name FROM terms_master WHERE sub_category = ?", (s_sel,))
                m_terms = [r[0] for r in cur.fetchall()]
            except Exception:
                m_terms = []

            # term_categories から所属用語を重複なく取得
            try:
                cur.execute("""
                SELECT DISTINCT term_name FROM term_categories 
                WHERE sub_category = ? 
                ORDER BY term_name
                """, (s_sel,))
                t_terms = [r[0] for r in cur.fetchall()]
            except Exception:
                # テーブル未作成時のフォールバック
                cur.execute("SELECT DISTINCT term_name FROM terms WHERE sub_category = ? ORDER BY term_name", (s_sel,))
                t_terms = [r[0] for r in cur.fetchall()]

            # terms_master 優先で結合
            f_terms = m_terms + [t for t in t_terms if t not in m_terms]

            if f_terms:
                def_idx = f_terms.index(st.session_state.current_term) if st.session_state.current_term in f_terms else 0
                chosen = st.selectbox(f"3. 対象用語（{len(f_terms)}件）：", options=f_terms, index=def_idx)
                st.session_state.current_term = chosen
            else:
                st.info(f"「{s_sel}」の登録用語は現在0件です。")

        conn.close()

    st.markdown("---")
    if st.button("ログアウト"):
        st.session_state.logged_in = False
        st.session_state.app_mode = "ホーム"
        st.session_state.quiz_active = False
        st.rerun()

# ==========================================
# 4. メイン画面の分岐
# ==========================================

# --- [A] ホーム画面 ---
if st.session_state.app_mode == "ホーム":
    st.markdown(f'<h1 class="notranslate" translate="no">ようこそ、{st.session_state.user_name} さん！ 👋</h1>', unsafe_allow_html=True)
    st.write("基本情報技術者試験（科目A）の対策を始めましょう。学習目的を選択してください。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📖 用語を勉強する\nシラバス全23分類の「公式定義」「直感的な例え話」「身近な実用例」の解説を載せています。")
        if st.button("用語学習へ進む ➔", key="btn_go_study", type="primary"):
            st.session_state.app_mode = "用語を勉強する"
            st.rerun()
            
    with col2:
        st.success("### 📝 問題を解く\n`terms_master` に収録された予想問題に挑戦。文系・情報科学科それぞれの属性に最適化されたAI誤答解説付き。")
        if st.button("問題演習へ進む ➔", key="btn_go_quiz", type="primary"):
            st.session_state.app_mode = "問題を解く"
            st.rerun()

# --- [B] 用語学習画面 ---
elif st.session_state.app_mode == "用語を勉強する":
    curr = st.session_state.current_term

    conn = get_db()
    cur = conn.cursor()

    master_data = None
    try:
        cur.execute("""
        SELECT category, sub_category, intuitive_def, practical_example, official_def 
        FROM terms_master WHERE term_name = ?
        """, (curr,))
        master_data = cur.fetchone()
    except Exception:
        pass

    normal_data = None
    if not master_data:
        try:
            cur.execute("""
            SELECT category, sub_category, official_def 
            FROM terms WHERE term_name = ?
            """, (curr,))
            normal_data = cur.fetchone()
        except Exception:
            pass

    # 閲覧ログの記録
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
        cat_log = master_data[0] if master_data else (normal_data[0] if normal_data else "未分類")
        cur.execute("INSERT INTO term_logs (user_id, term_name, category) VALUES (?, ?, ?)",
                    (st.session_state.user_id, curr, cat_log))
        conn.commit()
    except Exception:
        pass
    conn.close()

    if master_data:
        cat, sub, int_def, prac_ex, off_def = master_data
        st.caption(f"📚 {cat} ＞ {sub} （★特製7項目データ完備）")
        st.markdown(f'<h1 class="notranslate" translate="no">💻 {curr}</h1>', unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["💡 直感理解（例え話）", "🌍 身近な実用例", "📖 試験対策（公式定義）"])

        with tab1:
            st.subheader("身近なたとえ話")
            st.info(int_def if int_def else "※解説準備中")

        with tab2:
            st.subheader("社会やサービスでの実用例")
            st.success(prac_ex if prac_ex else "※実用例準備中")

        with tab3:
            st.subheader("シラバス・教科書的定義")
            st.warning(off_def if off_def else "※公式定義準備中")

    elif normal_data:
        cat, sub, off_def = normal_data
        st.caption(f"📚 {cat} ＞ {sub}")
        st.markdown(f'<h1 class="notranslate" translate="no">💻 {curr}</h1>', unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["📖 シラバス公式解説", "💡 直感理解（例え話）", "🌍 身近な実用例"])

        with tab1:
            st.subheader("公式定義・過去問道場アーカイブ解説")
            st.write(off_def if off_def else "※公式定義準備中")

        with tab2:
            st.subheader("身近なたとえ話")
            st.info("※この用語の例え話は自動生成拡張待ちです。")

        with tab3:
            st.subheader("社会やサービスでの実用例")
            st.success("※この用語の実用例は自動生成拡張待ちです。")

    else:
        st.warning(f"「{curr}」のデータが見つかりませんでした。")

# --- [C] 問題演習画面 ---
elif st.session_state.app_mode == "問題を解く":
    st.markdown('<h1 class="notranslate" translate="no">📝 実戦問題演習モード（科目A試験対策）</h1>', unsafe_allow_html=True)

    if not st.session_state.quiz_active:
        st.subheader("演習設定")
        st.caption("`terms_master` に収録された予想問題から出題されます。")

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM terms_master WHERE question_text IS NOT NULL AND question_text != ''")
            avail_q_count = cur.fetchone()[0]
        except Exception:
            avail_q_count = 0
        conn.close()

        if avail_q_count == 0:
            st.warning("現在出題可能な問題がありません。先に `python3 import_and_complete_16terms.py` を実行してください。")
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
                st.success("🏆 合格基準点（60%）達成！ 素晴らしい仕上がりです。")
            else:
                st.info("💡 基準点は60%です。学習者別解説を復習して再挑戦しましょう。")

            st.markdown("---")
            st.subheader("📋 解答一覧と詳細解説")
            for i, q in enumerate(q_list):
                q_id, q_term, q_text, c_a, c_b, c_c, c_d, c_ans, exp_beg, exp_adv = q
                ans_data = st.session_state.quiz_user_answers.get(i, {})
                with st.expander(f"問 {i+1}：{q_term} — {'✅ 正解' if ans_data.get('is_correct') else '❌ 不正解'}"):
                    st.write(f"**問題：** {q_text}")
                    st.write(f"**あなたの回答：** {ans_data.get('selected')} ｜ **正解：** {c_ans}")
                    
                    sub_t1, sub_t2 = st.tabs(["🌱 初心者・文系向け解説", "🔬 情報科学科向け解説"])
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
            st.markdown(f'<h3 class="notranslate" translate="no">Q{idx + 1}. {q_text}</h3>', unsafe_allow_html=True)

            choices = [f"ア. {c_a}", f"イ. {c_b}", f"ウ. {c_c}", f"エ. {c_d}"]
            user_choice = st.radio("選択肢：", choices, key=f"q_radio_{idx}", disabled=st.session_state.quiz_answered_current)
            selected_char = user_choice[0]

            if not st.session_state.quiz_answered_current:
                if st.button("回答を送信する", type="primary"):
                    is_correct = (selected_char == c_ans)
                    st.session_state.quiz_user_answers[idx] = {
                        "question_id": q_id,
                        "selected": selected_char,
                        "is_correct": is_correct
                    }
                    st.session_state.quiz_answered_current = True

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