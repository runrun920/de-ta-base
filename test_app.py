import streamlit as st
import sqlite3
import random
import os
import logging
import pandas as pd
import time
import streamlit.components.v1 as components

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
TEST_LIMIT_SECONDS = 7 * 60  # 制限時間：7分（420秒）

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

# ---------------------------------------------------------
# 2. テスト用テーブルの初期化＆問題データの自動登録
# ---------------------------------------------------------
@st.cache_resource
def init_and_setup_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS questions")
    cur.execute("DROP TABLE IF EXISTS terms")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT UNIQUE,
        sub_category TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        question_text TEXT,
        choice_a TEXT,
        choice_b TEXT,
        choice_c TEXT,
        choice_d TEXT,
        correct_ans TEXT,
        explanation TEXT,
        is_pretest INTEGER DEFAULT 0,
        is_posttest INTEGER DEFAULT 0,
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        test_type TEXT,
        question_id INTEGER,
        term_name TEXT,
        sub_category TEXT,
        selected_choice TEXT,
        correct_ans TEXT,
        is_correct INTEGER,
        answered_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

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

    # 事前テストデータ（10問）
    pretest_data = [
        ("プログラムの格納場所", "コンピュータ構成要素", "コンピュータの電源投入時に最初に実行されるプログラムの格納に適しているものはどれか。ここで、主記憶のバッテリバックアップはしないものとする。", "DRAM", "HDD", "ROM", "SRAM", "ウ", ""),
        ("USBの特徴", "コンピュータ構成要素", "USBの特徴はどれか。", "PCなどの小型コンピュータと、磁気ディスク、レーザプリンターなどの周辺機器を接続するパラレルインタフェースである。", "音声や映像など、リアルタイム性の必要なデータ転送に適した高速な転送方法を採用しており、FireWireとも呼ばれている。", "シリアルインタフェースであり、元来はモデムを接続する規格であったが、PCと周辺機器を接続するのにも使われる。", "三つのデータ転送モードがあり、ハイスピードモードは外付け磁気ディスクなどの接続に使用される。", "エ", ""),
        ("チャレンジレスポンス認証", "セキュリティ", "二つの通信主体XとYの間で、次の手順の情報交換を行う認証はどれか。\n[手順]\n(1) Yは、任意の情報を含む文字列（チャレンジ）をXへ送信する。\n(2) Xは、あらかじめX、Y間で定めた規則に基づき、受け取った文字列から新たな文字列（レスポンス）を生成し、Yへ転送する。\n(3) Yは、返送されてきた文字列（レスポンス）が正しいことを確認する。", "XがYを認証する。", "XがYを認証することによって、結果としてYがXを認証する。", "YがXを認証する。", "YがXを認証することによって、結果としてXがYを認証する。", "ウ", "Yは、返送されてきたレスポンス文字列とチャレンジをXと同じ規則で変換した文字列を比較することでXが正当な通信相手であることを認証できます。しかし、X側にYから送られてくる情報は任意の文字列だけなのでXがYを認証する手立てはありません。したがって正しい記述は「YがXを認証する」になります。"),
        ("CSIRT", "セキュリティ", "CSIRTの説明として、適切なものはどれか。", "IPアドレスの割当て方針の決定、DNSルートサーバの運用監視、DNS管理に関する調整などを世界規模で行う組織である。", "インターネットに関する技術文書を作成し、標準化のための検討を行う組織である。", "企業内・組織内や政府機関に設置され、情報セキュリティインシデントに関する報告を受け取り、調査し、対応活動を行う組織の総称である。", "情報技術を利用し、宗教的又は政治的な目標を達成するという目的をもつ者や組織の総称である。", "ウ", ""),
        ("NAT機能", "ネットワーク", "IPv4において、インターネット接続用ルータのNAT機能の説明として、適切なものはどれか。", "インターネットへのアクセスをキャッシュしておくことによって、その後に同じIPアドレスのWebサイトへアクセスする場合、表示を高速化できる機能である。", "通信中のIPパケットを検査して、インターネットからの攻撃や侵入を検知する機能。", "特定の端末宛てのIPパケットだけを通過させる機能である。", "プライベートIPアドレスとグローバルIPアドレスを相互に変換する機能である。", "エ", "NAT(Network Address Translation)とは、プライベートIPアドレスとグローバルIPアドレスを1対1で相互に変換する技術です。複数の端末が同時にインターネットに接続する場合には、それに対応する数のグローバルIPアドレスが必要になります。"),
        ("ビューの性質", "データベース", "関係データベース管理システム(RDBMS)におけるビューに関する記述のうち、適切なものはどれか。", "ビューとは、名前を付けた導出表のことである。", "ビューに対して、ビューを定義することはできない。", "ビューの定義を行ってから、必要があれば、その基底表を定義する。", "ビューは一つの基底表に対して一つだけ定義できる。", "ア", ""),
        ("主キーの性質", "データベース", "関係データベースの主キーの性質として、適切なものはどれか。", "主キーとして列に対して検索条件を指定しなければ、行の検索はできない。", "数値型の列を主キーに指定すると、その列は算術演算の対象としては使えない。", "一つの表の中に、主キーの値が同じ行が複数存在することはない。", "複数の列からなる主キーを構成することができない。", "ウ", ""),
        ("コンパイラの処理順序", "ソフトウェア", "手続型言語のコンパイラが行う処理のうち、最初に行う処理はどれか。", "意味解析", "構文解析", "最適化", "字句解析", "エ", ""),
        ("モジュール強度", "システム開発技術", "モジュール設計書を基にモジュール強度を評価した。適切な評価はどれか。\n[モジュール設計書（抜粋）]\n上位モジュールから渡される処理コードに対応した処理をする。処理コードが”I”のときは、挿入処理、処理コードが”U”のときは更新処理、処理コードが”D”のときは削除処理である。", "これは”暗号的強度”のモジュールである。モジュール内の機能間に特別な関係はなく、むしろ他のモジュールとの強い関係性をもつ可能性が高いので、モジュール分割をやり直した方が良い。", "これは”情報的強度”のモジュールである。同一の情報を扱う複数の機能を、一つのモジュールにまとめている。モジュール内に各処理の入口点を設けているので、制御の結びつきがなく、これ以上のモジュール分割は不要である。", "これは”連絡的強度”のモジュールである。モジュール内でデータの受け渡し又は参照を行いながら、複数の機能を逐次的に実行している。再度見直しを図り、必要に応じて更にモジュール分割を行ったほうが良い。", "これは”論理的強度”のモジュールである。関連したいくつかの機能を含み、パラメータによっていずれかの機能を選択して実行している。現状では大きな問題となっていないとしても、仕様変更に伴うパラメータの変更による影響を最小限に抑えるために、機能ごとにモジュールを分割するか、機能ごとの入口点を設ける方が良い。", "エ", ""),
        ("親和図法", "企業活動", "親和図法を説明したものはどれか。", "事象の進展とともに様々な事象が想定される問題について対応策を検討し、望ましい結果に至るプロセスを定める方法である。", "収集した情報を相互の関連によってグループ化し、解決すべき問題点を明確にする方法である。", "複雑な要因の絡み合う事象について、その事象間の因果関係を明らかにする方法である。", "目的・目標を達成するための手段・方策を順次展開し、最適な手段・方策を追求していく方法である。", "イ", "")
    ]

    # 事後テストデータ（10問）
    posttest_data = [
        ("ページプリンター", "コンピュータ構成要素", "ページプリンターで、画像と漢字コードが混在しているデータを印刷するための処理方法に関する記述として、適切なものはどれか。", "パソコンが漢字データをビットマップ形式に展開した後、プリンターが画像と合成して、ライン単位で印刷イメージを作る。", "プリンターが画像と漢字データをラインごとのビット列に展開して、ラインごとに順次印刷する。", "プリンターが画像をビットマップ形式に展開して印刷イメージを作り、漢字フォントにはパソコンのフォントファイルを使用する。", "プリンター又はパソコンのプリンタードライバのどちらかが、画像と漢字データをビットマップ形式に展開して、印刷イメージを作る。", "エ", ""),
        ("ROE", "コンピュータ構成要素", "ROEを説明したものはどれか。", "企業が保有する総資産に対する収益性を示す指標", "自己資本と総資本の比率から、財務体質の健全性を示す指標", "自己資本と他人資本の有効活用の度合いを図る指標", "自己資本に対する収益性を示す指標", "エ", ""),
        ("WAF", "セキュリティ", "WAFの説明はどれか。", "Webアプリケーションへの攻撃を検知し、阻止する。", "Webブラウザの通信内容を改ざんする攻撃をPC内で監視し、検出する。", "サーバのOSへの不正なログインを監視する。", "ファイルへのマルウェア感染を監視し、検出する。", "ア", ""),
        ("パターンマッチング方式", "セキュリティ", "ウイルス対策ソフトのパターンマッチング方式を説明したものはどれか。", "感染前のファイルと感染後のファイルを比較し、ファイルに変更が加わったかどうかを調べてウイルスを検出する。", "既知ウイルスのシグネチャと比較して、ウイルスを検出する。", "システム内でのウイルスに起因する異常現象を監視することによって、ウイルスを検出する。", "ファイルのチェックサムと照合して、ウイルスを検出する。", "イ", ""),
        ("電子メール送信プロトコル", "ネットワーク", "利用者のPCから電子メールを送信するときや、メールサーバ間で電子メールを転送するときに使われるプロトコルはどれか。", "IMAP", "MIME", "POP3", "SMTP", "エ", ""),
        ("機械学習の適用事例", "データベース", "蓄積されたデータに対してパターン認識機能や機械学習機能を適用することによって、コールセンターにおける顧客応対業務の質的向上が可能となる事例はどれか。", "応対マニュアルや顧客の基本情報を電子化したものを、オペレーターの要求時に応対用の画面にポップアップ画面として表示する。", "顧客の問い合わせの内容に応じて、関連資料や過去の応対に関する全履歴から、最適な回答をリアルタイムで導き出す。", "電話応対中のオペレーターが回答に窮したときに、その電話や応対画面をベテランのオペレーターや専門要員に転送する。", "ベテランのオペレーターが講師となり、応対マニュアルを教材にして、新人オペレーターに対するロールプレイング研修を繰り返して実施する。", "イ", ""),
        ("ワークサンプリング法", "データベース", "ワークサンプリング法の説明として、適切なものはどれか。", "1サイクルの作業時間が短い場合や観測前に作業を分割できる場合に、その作業時間をストップウォッチで測定する。", "ある時点での観測対象が、作業内容のどの状態にあったかという瞬間観測を何回か行い、観察記録の回数の割合から、各作業時間がどのくらいであるかを推定する。", "観測対象の作業内容を基本動作にまで分解・分析し、作業条件ごとに設定した基本動作の標準時間から作業時間を割り出す。", "職長や班長などが経験的判断によって作業時間を求める。", "イ", ""),
        ("管理図", "ソフトウェア", "管理図を説明したものはどれか。", "原因と結果の関連を魚の骨のような形状として体系的にまとめ、結果に対してどのような原因が関連しているかを明確にする。", "時系列的に発生するデータのばらつきを折れ線グラフで表し、上限と下限を設定して異常の発見に用いる。", "収集したデータを幾つかの区間に分類し、各区間に属するデータの個数を棒グラフとして描き、品質のばらつきをとらえる。", "データを幾つかの項目に分類し、横軸方向に大きい順に棒グラフとして並べ、累積値を折れ線グラフで描き、主要な問題点を把握する。", "イ", ""),
        ("貸借対照表", "システム開発技術", "貸借対照表を説明したものはどれか。", "一定期間における、現金・預金の収入・支出を示したもの。", "一定期間における、資金の調達と運用を示したもの。", "会計期間に属するすべての収益と費用を記載し、算出した利益を示したもの。", "会計期間の期末日時点での財政状態を示したもの。", "エ", ""),
        ("発注方式", "企業活動", "発注方式に関する記述のうち、適切なものはどれか。", "単価が高く、調達期間が長い商品は、定期発注方式より定量発注方式の方が適している", "定期発注方式は、多くの商品を同時に発注でき、在庫量の減少を図ることもできる。", "定量発注方式では、毎回需要予測を行って発注量を決める。", "二棚法を用いて発注を行うと、発注事務作業が容易にでき、需要の変化に的確に対応できる。", "イ", "")
    ]

    for item in pretest_data:
        t_name, sub_cat, q_text, c_a, c_b, c_c, c_d, c_ans, exp = item
        cur.execute("INSERT OR IGNORE INTO terms (term_name, sub_category) VALUES (?, ?)", (t_name, sub_cat))
        cur.execute("SELECT id FROM terms WHERE term_name = ?", (t_name,))
        term_id = cur.fetchone()[0]

        cur.execute("""
        INSERT INTO questions (term_id, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, explanation, is_pretest, is_posttest)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """, (term_id, q_text, c_a, c_b, c_c, c_d, c_ans, exp))

    for item in posttest_data:
        t_name, sub_cat, q_text, c_a, c_b, c_c, c_d, c_ans, exp = item
        cur.execute("INSERT OR IGNORE INTO terms (term_name, sub_category) VALUES (?, ?)", (t_name, sub_cat))
        cur.execute("SELECT id FROM terms WHERE term_name = ?", (t_name,))
        term_id = cur.fetchone()[0]

        cur.execute("""
        INSERT INTO questions (term_id, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, explanation, is_pretest, is_posttest)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
        """, (term_id, q_text, c_a, c_b, c_c, c_d, c_ans, exp))

    conn.commit()
    conn.close()

init_and_setup_db()

# ---------------------------------------------------------
# 3. セッション状態の初期化
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_name = ""
    st.session_state.major_type = "文系・初学者"

if "test_mode" not in st.session_state:
    st.session_state.test_mode = "HOME"

if "test_questions" not in st.session_state:
    st.session_state.test_questions = []
if "test_index" not in st.session_state:
    st.session_state.test_index = 0
if "test_user_answers" not in st.session_state:
    st.session_state.test_user_answers = {}
if "current_test_type" not in st.session_state:
    st.session_state.current_test_type = ""
if "start_time" not in st.session_state:
    st.session_state.start_time = None

# ---------------------------------------------------------
# 4. ログイン画面
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
# 5. サイドバー（常時表示）
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div translate="no">👤 被験者: <b>{st.session_state.user_name}</b> さん<br><small>ID: {st.session_state.user_id} ｜ {st.session_state.major_type}</small></div>', unsafe_allow_html=True)
    st.markdown("---")
    
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
# 6. 出題ロジック・共通提出関数
# ---------------------------------------------------------
def generate_test_questions(test_type):
    conn = get_db()
    cur = conn.cursor()
    
    if test_type == "事前テスト":
        query = """
        SELECT q.id, t.term_name, t.sub_category, q.question_text, 
               q.choice_a, q.choice_b, q.choice_c, q.choice_d, 
               q.correct_ans, q.explanation
        FROM questions q
        JOIN terms t ON q.term_id = t.id
        WHERE q.is_pretest = 1
        ORDER BY q.id ASC
        """
        cur.execute(query)
    elif test_type == "事後テスト":
        query = """
        SELECT q.id, t.term_name, t.sub_category, q.question_text, 
               q.choice_a, q.choice_b, q.choice_c, q.choice_d, 
               q.correct_ans, q.explanation
        FROM questions q
        JOIN terms t ON q.term_id = t.id
        WHERE q.is_posttest = 1
        ORDER BY q.id ASC
        """
        cur.execute(query)
    else:
        conn.close()
        return []

    questions = cur.fetchall()
    conn.close()
    return questions

def save_and_submit_test(test_type, total):
    """解答結果を保存しテストを提出完了にする共通関数"""
    conn = get_db()
    cur = conn.cursor()
    correct_count = 0
    
    q_list = st.session_state.test_questions
    for i, q in enumerate(q_list):
        q_id, q_term, q_sub_cat, q_text, c_a, c_b, c_c, c_d, c_ans, exp = q
        a_data = st.session_state.test_user_answers.get(i, {})
        selected_choice = a_data.get("selected_choice", "未解答")
        
        is_corr = 1 if selected_choice == c_ans.strip() else 0
        if is_corr:
            correct_count += 1
            
        cur.execute("""
        INSERT INTO test_logs (user_id, test_type, question_id, term_name, sub_category, selected_choice, correct_ans, is_correct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (st.session_state.user_id, test_type, q_id, q_term, q_sub_cat, selected_choice, c_ans, is_corr))
    
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

# JavaScriptによる完全独立型のタイマーコンポーネント
def render_javascript_timer(start_timestamp, limit_seconds):
    timer_html = f"""
    <div id="timer-box" style="text-align: right; font-size: 22px; font-weight: bold; color: darkorange; font-family: sans-serif;">
        ⏳ 残り時間: <span id="timer-text">--:--</span>
    </div>
    <script>
        const startTime = {start_timestamp};
        const limitSeconds = {limit_seconds};
        
        function updateTimer() {{
            const now = Math.floor(Date.now() / 1000);
            const elapsed = now - startTime;
            const remaining = Math.max(0, limitSeconds - elapsed);
            
            const mins = String(Math.floor(remaining / 60)).padStart(2, '0');
            const secs = String(remaining % 60).padStart(2, '0');
            
            const timerElem = document.getElementById("timer-text");
            const boxElem = document.getElementById("timer-box");
            if (timerElem) {{
                timerElem.innerText = mins + ":" + secs;
                if (remaining < 60) {{
                    boxElem.style.color = "red";
                }}
            }}
        }}
        updateTimer();
        setInterval(updateTimer, 1000);
    </script>
    """
    components.html(timer_html, height=45)

# ---------------------------------------------------------
# 7. メイン画面の挙動制御
# ---------------------------------------------------------

# 【1. ホーム画面】
if st.session_state.test_mode == "HOME":
    st.title("📝 効果測定システム（事前・事後テスト）")
    st.write("学習システムの利用効果を検証するため、学習前と学習後にそれぞれ10問のテストを行います。")
    st.warning("⏱️ **制限時間: 各テスト 7分（420秒）**")
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
                st.session_state.start_time = time.time()
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
                st.session_state.start_time = time.time()
                st.session_state.test_mode = "TEST_RUN"
                logger.info(f"POST_TEST_START: user_id={st.session_state.user_id}")
                st.rerun()
            if not can_start:
                st.caption("⚠️ 事前テスト完了後に開放されます。")

# 【2. テスト解答画面】
elif st.session_state.test_mode == "TEST_RUN":
    q_list = st.session_state.test_questions
    idx = st.session_state.test_index
    total = len(q_list)
    test_type = st.session_state.current_test_type

    # タイトルとJavaScriptタイマー表示
    col_title, col_timer = st.columns([2, 1])
    with col_title:
        st.markdown(f"## 📝 {test_type} （{idx + 1} / {total} 問）")
    with col_timer:
        render_javascript_timer(int(st.session_state.start_time), TEST_LIMIT_SECONDS)

    # タイムアップ（時間切れ）判定
    elapsed_time = time.time() - st.session_state.start_time
    if elapsed_time >= TEST_LIMIT_SECONDS:
        st.error("⏰ 制限時間の7分が経過しました。自動的に解答を提出します。")
        save_and_submit_test(test_type, total)
        st.rerun()
    
    if idx < total:
        q = q_list[idx]
        q_id, q_term, q_sub_cat, q_text, c_a, c_b, c_c, c_d, c_ans, exp = q

        st.progress((idx + 1) / total)
        
        st.markdown(f"### Q{idx + 1}. {q_text}")

        choices = [f"ア: {c_a}", f"イ: {c_b}", f"ウ: {c_c}", f"エ: {c_d}"]
        
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
                st.session_state.test_user_answers[idx] = {
                    "q_id": q_id, "term": q_term, "sub_cat": q_sub_cat,
                    "selected_choice": selected_char, "correct_ans": c_ans
                }
                
                if (idx + 1) < total:
                    st.session_state.test_index += 1
                    st.rerun()
                else:
                    save_and_submit_test(test_type, total)
                    st.rerun()

# 【3. 結果表示画面】
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