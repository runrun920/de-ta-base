import streamlit as st
import sqlite3
import random
import os
import logging
import pandas as pd
import time
import base64
import requests
import csv
import io
from datetime import datetime, timezone, timedelta
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

class GitHubLogHandler(logging.Handler):
    """ログが発生するたびにGitHubリポジトリ上のファイルへ追記するハンドラ"""
    def emit(self, record):
        log_entry = self.format(record) + "\n"
        try:
            token = st.secrets["GITHUB_TOKEN"]
            repo = st.secrets["GITHUB_REPO"]
            branch = st.secrets.get("GITHUB_BRANCH", "test")
            path = st.secrets.get("LOG_FILE_PATH", "test_app.log")
        except Exception:
            return

        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            res = requests.get(url, headers=headers, params={"ref": branch}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                sha = data["sha"]
                current_content = base64.b64decode(data["content"]).decode("utf-8")
            else:
                sha = None
                current_content = ""

            new_content = current_content + log_entry
            encoded_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

            payload = {
                "message": "Update test_app.log from Streamlit",
                "content": encoded_content,
                "branch": branch
            }
            if sha:
                payload["sha"] = sha

            requests.put(url, headers=headers, json=payload, timeout=5)
        except Exception:
            pass

def append_csv_to_github(filename, rows_list, header_list):
    """テスト結果や詳細解答履歴をGitHub上のCSVファイルに追記する関数"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        branch = st.secrets.get("GITHUB_BRANCH", "test")
    except Exception:
        return

    url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        res = requests.get(url, headers=headers, params={"ref": branch}, timeout=5)
        output = io.StringIO()
        writer = csv.writer(output)

        if res.status_code == 200:
            data = res.json()
            sha = data["sha"]
            current_content = base64.b64decode(data["content"]).decode("utf-8-sig")
            if current_content and not current_content.endswith("\n"):
                current_content += "\n"
        else:
            sha = None
            writer.writerow(header_list)
            current_content = output.getvalue()
            output = io.StringIO()
            writer = csv.writer(output)

        for row in rows_list:
            writer.writerow(row)

        new_content = current_content + output.getvalue()
        encoded_content = base64.b64encode(new_content.encode("utf-8-sig")).decode("utf-8")

        payload = {
            "message": f"Update {filename} from Streamlit",
            "content": encoded_content,
            "branch": branch
        }
        if sha:
            payload["sha"] = sha

        requests.put(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

def setup_logger():
    logger = logging.getLogger("FE_TEST_LOGGER")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        jst = timezone(timedelta(hours=9))
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        formatter.converter = lambda *args: datetime.now(jst).timetuple()

        fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        gh = GitHubLogHandler()
        gh.setFormatter(formatter)
        logger.addHandler(gh)
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

    # 事前テストデータ（7分野・10問：すべて語彙問題）
    pretest_data = [
        # 1. コンピュータ構成要素
        ("ROM", "コンピュータ構成要素",
         "コンピュータの電源投入時に最初に実行されるプログラムの格納に適しているものはどれか。ここで、主記憶のバッテリバックアップはしないものとする。",
         "DRAM", "HDD", "ROM", "SRAM", "ウ",
         "電源を切っても記憶内容が消えない不揮発性メモリであるROMに、起動用プログラム（BIOS/UEFI）を格納します。"),
        # 2. コンピュータ構成要素
        ("USB", "コンピュータ構成要素",
         "USBの特徴はどれか。",
         "PCなどの小型コンピュータと、磁気ディスク、レーザプリンターなどの周辺機器を接続するパラレルインタフェースである。",
         "音声や映像など、リアルタイム性の必要なデータ転送に適した高速な転送方法を採用しており、FireWireとも呼ばれている。",
         "シリアルインタフェースであり、元来はモデムを接続する規格であったが、PCと周辺機器を接続するのにも使われる。",
         "三つのデータ転送モードがあり、ハイスピードモードは外付け磁気ディスクなどの接続に使用される。", "エ",
         "USB 2.0ではロー・フル・ハイスピードの3つの転送モードがあり、ハイスピードモード（480Mbps）は外付け磁気ディスクなどの接続に使用されます。"),
        # 3. セキュリティ
        ("ソーシャルエンジニアリング", "セキュリティ",
         "ソーシャルエンジニアリングの説明として、適切なものはどれか。",
         "インターネット上のWebサイトに悪意のあるスクリプトを埋め込み、利用者のブラウザ上で実行させる攻撃である。",
         "技術的な手段を使わず、人間の心理的な隙や行動のミスにつけ込んで、パスワードや機密情報を不正に入手する手法である。",
         "大量のパケットを特定のサーバに送りつけ、システムを過負荷状態にしてサービスを停止させる攻撃である。",
         "利用者が入力したデータをそのままSQL文に組み込むことで、データベースを不正に操作する攻撃である。", "イ",
         "ソーシャルエンジニアリングは、肩越しに画面を覗き見る（ショルダーハッキング）や、なりすましの電話でパスワードを聞き出すなど、人間の心理的な隙を突く手法です。"),
        # 4. セキュリティ
        ("CSIRT", "セキュリティ",
         "CSIRTの説明として、適切なものはどれか。",
         "IPアドレスの割当て方針の決定、DNSルートサーバの運用監視、DNS管理に関する調整などを世界規模で行う組織である。",
         "インターネットに関する技術文書を作成し、標準化のための検討を行う組織である。",
         "企業内・組織内や政府機関に設置され、情報セキュリティインシデントに関する報告を受け取り、調査し、対応活動を行う組織の総称である。",
         "情報技術を利用し、宗教的又は政治的な目標を達成するという目的をもつ者や組織の総称である。", "ウ",
         "CSIRT（Computer Security Incident Response Team）は、セキュリティインシデント発生時の報告受付・調査・対応を行う専門組織です。"),
        # 5. ネットワーク
        ("NAT", "ネットワーク",
         "IPv4において、インターネット接続用ルータのNAT機能の説明として、適切なものはどれか。",
         "インターネットへのアクセスをキャッシュしておくことによって、その後に同じIPアドレスのWebサイトへアクセスする場合、表示を高速化できる機能である。",
         "通信中のIPパケットを検査して、インターネットからの攻撃や侵入を検知する機能。",
         "特定の端末宛てのIPパケットだけを通過させる機能である。",
         "プライベートIPアドレスとグローバルIPアドレスを相互に変換する機能である。", "エ",
         "NAT（Network Address Translation）は、プライベートIPアドレスとグローバルIPアドレスを相互に変換する技術です。"),
        # 6. データベース
        ("ビュー", "データベース",
         "関係データベース管理システム(RDBMS)におけるビューに関する記述のうち、適切なものはどれか。",
         "ビューとは、名前を付けた導出表のことである。",
         "ビューに対して、ビューを定義することはできない。",
         "ビューの定義を行ってから、必要があれば、その基底表を定義する。",
         "ビューは一つの基底表に対して一つだけ定義できる。", "ア",
         "ビューは実データを保持せず、SELECT文などの問合せ定義に名前を付けた仮想的な表（導出表）です。"),
        # 7. データベース
        ("主キー", "データベース",
         "関係データベースの主キーの性質として、適切なものはどれか。",
         "主キーとして列に対して検索条件を指定しなければ、行の検索はできない。",
         "数値型の列を主キーに指定すると、その列は算術演算の対象としては使えない。",
         "一つの表の中に、主キーの値が同じ行が複数存在することはない。",
         "複数の列からなる主キーを構成することができない。", "ウ",
         "主キーは表内の行を一意に識別するための制約（一意性制約・非NULL制約）を持つため、同じ値が重複することはありません。"),
        # 8. ソフトウェア
        ("コンパイラ", "ソフトウェア",
         "手続型言語のコンパイラが行う処理のうち、最初に行う処理はどれか。",
         "意味解析", "構文解析", "最適化", "字句解析", "エ",
         "コンパイラは最初にソースコードを意味のある最小単位（トークン）に分解する「字句解析」を行います。"),
        # 9. システム開発技術
        ("ブラックボックステスト", "システム開発技術",
         "ブラックボックステストの説明として、適切なものはどれか。",
         "プログラムの内部構造や制御フローに注目し、すべての命令や分岐が正しく実行されるかを確認するテストである。",
         "プログラムの内部構造には着目せず、外部から見た仕様（入力と出力の関係）どおりに機能するかを確認するテストである。",
         "プログラムを修正した際に、その影響で既存の正常だった機能に不具合が生じていないかを確認するテストである。",
         "開発者が作成したシステムを、実際の業務データを用いて発注者（利用者）が操作し、要件を満たすかを確認するテストである。", "イ",
         "ブラックボックステストは、システムの内部処理をブラックボックス（中身が見えない箱）とみなし、入力データに対して仕様どおりの出力が得られるかを検証するテストです。"),
        # 10. 企業活動
        ("親和図法", "企業活動",
         "親和図法を説明したものはどれか。",
         "事象の進展とともに様々な事象が想定される問題について対応策を検討し、望ましい結果に至るプロセスを定める方法である。",
         "収集した情報を相互の関連によってグループ化し、解決すべき問題点を明確にする方法である。",
         "複雑な要因の絡み合う事象について、その事象間の因果関係を明らかにする方法である。",
         "目的・目標を達成するための手段・方策を順次展開し、最適な手段・方策を追求していく方法である。", "イ",
         "親和図法（KJ法）は、収集した定性的な言語データを親和性（関連性）によってグループ化し、問題点を整理する手法です。")
    ]

    # 事後テストデータ（7分野・10問：すべて語彙問題）
    posttest_data = [
        # 1. コンピュータ構成要素
        ("DMA", "コンピュータ構成要素",
         "DMA（Direct Memory Access）の説明として、適切なものはどれか。",
         "CPUを介さずに、主記憶と入出力装置の間で直接データ転送を行う方式である。",
         "主記憶のアクセス速度とCPUの処理速度の差を埋めるために、高速な小容量メモリを配置する方式である。",
         "主記憶の空き領域を結合して、連続した大きな空き領域を確保する処理である。",
         "補助記憶装置の一部を主記憶のように扱い、実記憶容量以上のメモリ空間を提供する方式である。", "ア",
         "DMAはCPUの制御を介さず、専用のDMAコントローラによって主記憶と周辺機器間で直接データ転送を行う方式です。"),
        # 2. コンピュータ構成要素
        ("RAID5", "コンピュータ構成要素",
         "RAIDのレベルのうち、パリティと呼ばれる誤り訂正符号をデータとともに複数の磁気ディスクに分散して書き込む方式はどれか。",
         "RAID 0", "RAID 1", "RAID 5", "RAID 6", "ウ",
         "RAID 5はデータとパリティ（誤り訂正符号）を全ディスクに分散して記録し、1台の故障までデータを復旧できる方式です。"),
        # 3. セキュリティ
        ("WAF", "セキュリティ",
         "WAFの説明はどれか。",
         "Webアプリケーションへの攻撃を検知し、阻止する。",
         "Webブラウザの通信内容を改ざんする攻撃をPC内で監視し、検出する。",
         "サーバのOSへの不正なログインを監視する。",
         "ファイルへのマルウェア感染を監視し、検出する。", "ア",
         "WAF（Web Application Firewall）は、HTTP/HTTPS通信の内容を検査し、SQLインジェクションなどのWebアプリへの攻撃を遮断します。"),
        # 4. セキュリティ
        ("ランサムウェア", "セキュリティ",
         "ランサムウェアの説明として、適切なものはどれか。",
         "感染したPC内のファイルを暗号化するなどして利用不能にし、復号と引換えに金銭を要求するマルウェアである。",
         "感染したPCのキーボード入力を密かに記録し、IDやパスワードを外部へ送信するマルウェアである。",
         "正規のソフトウェアに見せかけて利用者にインストールさせ、バックドアを作成するマルウェアである。",
         "ネットワークを介して自己増殖を繰り返し、通信帯域を圧迫するマルウェアである。", "ア",
         "ランサムウェアはデータを暗号化したり画面をロックしたりして使用不能にし、身代金（Ransom）を要求するマルウェアです。"),
        # 5. ネットワーク
        ("SMTP", "ネットワーク",
         "利用者のPCから電子メールを送信するときや、メールサーバ間で電子メールを転送するときに使われるプロトコルはどれか。",
         "IMAP", "MIME", "POP3", "SMTP", "エ",
         "SMTP（Simple Mail Transfer Protocol）は電子メールの送信およびメールサーバ間の転送に用いられるプロトコルです。"),
        # 6. データベース
        ("正規化", "データベース",
         "関係データベースの正規化を行う目的として、適切なものはどれか。",
         "データの重複を排除し、データの更新に伴う矛盾や不整合が生じるのを防ぐこと。",
         "データを暗号化して、権限のない利用者による不正な閲覧を防ぐこと。",
         "表のデータを複数のディスクに分散配置して、検索速度を向上させること。",
         "障害発生時にトランザクションをロールバックして、データベースを元の状態に戻すこと。", "ア",
         "正規化は、属性間の関数従属性に基づいて表を分割することでデータの冗長性（重複）をなくし、更新時異常を防ぐ設計手法です。"),
        # 7. データベース
        ("外部キー", "データベース",
         "関係データベースにおける外部キー（参照整合性制約）の説明として、適切なものはどれか。",
         "ある表の列の値が、別の表（または同じ表）の主キーの値と一致するか、またはNULLでなければならないという制約である。",
         "一つの表の中で、指定された列の値が重複してはならないという制約である。",
         "表のすべての行において、指定された列に必ず値が存在し、NULLであってはならないという制約である。",
         "列に格納される値が、あらかじめ指定された条件式や範囲を満たさなければならないという制約である。", "ア",
         "外部キーは他の表の主キーを参照する列であり、参照先に存在しない値の登録などを防ぐ参照整合性制約を保ちます。"),
        # 8. ソフトウェア
        ("スプーリング", "ソフトウェア",
         "スプーリングの説明として、適切なものはどれか。",
         "処理速度の遅い入出力装置へのデータを、高速な補助記憶装置に一時的に書き出してから順次出力することで、システム全体の処理効率を高める機能である。",
         "主記憶上で断片化した未使用領域を回収し、連続した一つの大きな空き領域にまとめる機能である。",
         "複数のプログラムを同時に主記憶に読み込み、CPUの実行権を短い時間間隔で切り替えながら並行処理する機能である。",
         "頻繁にアクセスされるデータを主記憶の一部に保持し、補助記憶装置へのアクセス回数を減らす機能である。", "ア",
         "スプーリングは、低速なプリンタなどへの出力データを一旦磁気ディスクに蓄え、CPUを解放して並行処理させる技術です。"),
        # 9. システム開発技術
        ("レグレッションテスト", "システム開発技術",
         "レグレッションテスト（回帰テスト）の説明として、適切なものはどれか。",
         "プログラムの修正や機能追加を行ったときに、その変更によって既存の正常だった機能に悪影響（不具合）が生じていないかを確認するテストである。",
         "システムの内部構造や論理経路を分析し、すべての分岐や命令が少なくとも1回は実行されることを確認するテストである。",
         "開発者が作成したプログラムを、実際の運用環境に近い状態で発注者（利用者）が操作し、要件を満たしているかを確認するテストである。",
         "システムに大量のデータや多数の同時アクセスを与え、限界性能や負荷耐性を確認するテストである。", "ア",
         "レグレッションテスト（退行テスト・回帰テスト）は、プログラム保守や改修後に既存機能へのデグレード（先祖返り不具合）がないか検証するテストです。"),
        # 10. 企業活動
        ("パレート図", "企業活動",
         "パレート図を説明したものはどれか。",
         "原因と結果の関連を魚の骨のような形状として体系的にまとめ、結果に対してどのような原因が関連しているかを明確にする。",
         "時系列的に発生するデータのばらつきを折れ線グラフで表し、上限と下限を設定して異常の発見に用いる。",
         "収集したデータを幾つかの区間に分類し、各区間に属するデータの個数を棒グラフとして描き、品質のばらつきをとらえる。",
         "データを幾つかの項目に分類し、横軸方向に大きい順に棒グラフとして並べ、累積値を折れ線グラフで描き、主要な問題点を把握する。", "エ",
         "パレート図は、項目別の度数を降順の棒グラフで、累積構成比を折れ線グラフで表し、重視すべき主要因（ABC分析など）を特定する図です。")
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
                
                logger.info(f"TEST_USER_LOGIN: user_id={input_uid.strip()}, name={input_name.strip()}, major={input_major}")
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
    """解答結果をローカルDBとGitHub CSVの両方に保存する共通関数"""
    conn = get_db()
    cur = conn.cursor()
    correct_count = 0
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
    
    q_list = st.session_state.test_questions
    detail_csv_rows = []

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

        detail_csv_rows.append([
            now_str,
            st.session_state.user_id,
            st.session_state.user_name,
            test_type,
            q_sub_cat,
            q_term,
            selected_choice,
            c_ans.strip(),
            "○" if is_corr else "×"
        ])
    
    acc_rate = (correct_count / total) * 100
    cur.execute("""
    INSERT INTO test_results (user_id, test_type, score, total_questions, accuracy_rate)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(user_id, test_type) DO UPDATE SET score=?, accuracy_rate=?, completed_at=CURRENT_TIMESTAMP
    """, (st.session_state.user_id, test_type, correct_count, total, acc_rate, correct_count, acc_rate))
    
    conn.commit()
    conn.close()

    # GitHubへ詳細解答履歴とテスト結果をCSV保存
    append_csv_to_github(
        "test_logs.csv",
        detail_csv_rows,
        ["解答日時", "学籍番号_ID", "アカウント名", "テスト種別", "分野", "対象用語", "選択解答", "正解", "正誤"]
    )
    append_csv_to_github(
        "test_results.csv",
        [[now_str, st.session_state.user_id, st.session_state.user_name, st.session_state.major_type, test_type, correct_count, total, round(acc_rate, 1)]],
        ["完了日時", "学籍番号_ID", "アカウント名", "専攻", "テスト種別", "点数", "満点", "正答率"]
    )
    
    logger.info(f"TEST_COMPLETED: user={st.session_state.user_id}, type={test_type}, score={correct_count}/{total}")
    st.session_state.test_mode = "RESULT_VIEW"

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

elif st.session_state.test_mode == "TEST_RUN":
    q_list = st.session_state.test_questions
    idx = st.session_state.test_index
    total = len(q_list)
    test_type = st.session_state.current_test_type

    col_title, col_timer = st.columns([2, 1])
    with col_title:
        st.markdown(f"## 📝 {test_type} （{idx + 1} / {total} 問）")
    with col_timer:
        render_javascript_timer(int(st.session_state.start_time), TEST_LIMIT_SECONDS)

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
