import sqlite3
import pandas as pd
import os

CSV_FILE = "fe_study_master.csv"
XLSX_FILE = "fe_study_master_23sheets.xlsx"
DB_FILE = "fe_study.db"

def make_database():
    if os.path.exists(XLSX_FILE):
        print(f"1. {XLSX_FILE} から読み込み中...")
        excel = pd.ExcelFile(XLSX_FILE)
        dfs = [pd.read_excel(XLSX_FILE, sheet_name=s) for s in excel.sheet_names if s != "全用語一覧"]
        df = pd.concat(dfs, ignore_index=True)
    elif os.path.exists(CSV_FILE):
        print(f"1. {CSV_FILE} から読み込み中...")
        df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")
    else:
        print("エラー: ソースファイルが見つかりません。")
        return

    print(f"2. 正規化データベース（{DB_FILE}）を再構築中...")
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # 既存のビュー・テーブルを整理
    cur.execute("DROP VIEW IF EXISTS terms_master")
    cur.execute("DROP TABLE IF EXISTS terms_master")
    cur.execute("DROP TABLE IF EXISTS question_explanations_beginner")
    cur.execute("DROP TABLE IF EXISTS question_explanations_advanced")
    cur.execute("DROP TABLE IF EXISTS question_explanations")
    cur.execute("DROP TABLE IF EXISTS questions")
    cur.execute("DROP TABLE IF EXISTS term_metaphors")
    cur.execute("DROP TABLE IF EXISTS term_examples")
    cur.execute("DROP TABLE IF EXISTS term_categories")
    cur.execute("DROP TABLE IF EXISTS terms")

    # 1. 用語マスター (3,342語)
    cur.execute("""
    CREATE TABLE terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT UNIQUE,
        category TEXT,
        sub_category TEXT,
        official_def TEXT,
        url TEXT
    )
    """)

    # 2. 比喩・例え話 専用テーブル
    cur.execute("""
    CREATE TABLE term_metaphors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        metaphor_text TEXT,
        source_ai TEXT,
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    # 3. 身近な実用例 専用テーブル
    cur.execute("""
    CREATE TABLE term_examples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        example_text TEXT,
        source_ai TEXT,
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    # 4. 4択問題テーブル
    cur.execute("""
    CREATE TABLE questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        question_text TEXT,
        choice_a TEXT,
        choice_b TEXT,
        choice_c TEXT,
        choice_d TEXT,
        correct_ans TEXT,
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    # 5-A. 文系・初学者向け解説 専用テーブル
    cur.execute("""
    CREATE TABLE question_explanations_beginner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        explanation TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)

    # 5-B. 情報科学科・理系向け解説 専用テーブル
    cur.execute("""
    CREATE TABLE question_explanations_advanced (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        explanation TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)

    # 6. 分類絞り込み用テーブル
    cur.execute("""
    CREATE TABLE term_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT,
        category TEXT,
        sub_category TEXT
    )
    """)

    # 7. アプリ互換用 VIEW (app.py は修正なしでそのまま動作)
    cur.execute("""
    CREATE VIEW terms_master AS
    SELECT 
        q.id AS id,
        t.term_name,
        t.category,
        t.sub_category,
        t.official_def,
        m.metaphor_text AS intuitive_def,
        e.example_text AS practical_example,
        q.question_text,
        q.choice_a,
        q.choice_b,
        q.choice_c,
        q.choice_d,
        q.correct_ans,
        qeb.explanation AS explanation_beginner,
        qea.explanation AS explanation_advanced
    FROM questions q
    JOIN terms t ON q.term_id = t.id
    LEFT JOIN term_metaphors m ON t.id = m.term_id AND m.source_ai = 'Final'
    LEFT JOIN term_examples e ON t.id = e.term_id AND e.source_ai = 'Final'
    LEFT JOIN question_explanations_beginner qeb ON q.id = qeb.question_id
    LEFT JOIN question_explanations_advanced qea ON q.id = qea.question_id
    """)

    for _, row in df.iterrows():
        t_name = str(row.get("term_name", "")).strip()
        if not t_name or t_name == "nan":
            continue

        cat = str(row.get("category", "")).strip()
        sub_cat = str(row.get("sub_category", "")).strip()
        off_def = str(row.get("kakomon_official_def", "")).strip()
        url = str(row.get("kakomon_url", "")).strip()

        cur.execute("""
        INSERT OR IGNORE INTO terms (term_name, category, sub_category, official_def, url)
        VALUES (?, ?, ?, ?, ?)
        """, (t_name, cat, sub_cat, off_def, url))
        
        cur.execute("SELECT id FROM terms WHERE term_name = ?", (t_name,))
        term_id = cur.fetchone()[0]

        cur.execute("INSERT INTO term_categories (term_name, category, sub_category) VALUES (?, ?, ?)",
                    (t_name, cat, sub_cat))

        # 比喩テーブル
        int_f = str(row.get("intuitive_def_final", "")).strip()
        if int_f and int_f != "nan":
            cur.execute("INSERT INTO term_metaphors (term_id, metaphor_text, source_ai) VALUES (?, ?, 'Final')", (term_id, int_f))

        # 実用例テーブル
        prac_f = str(row.get("practical_example_final", "")).strip()
        if prac_f and prac_f != "nan":
            cur.execute("INSERT INTO term_examples (term_id, example_text, source_ai) VALUES (?, ?, 'Final')", (term_id, prac_f))

        # 問題テーブル
        q_text = str(row.get("question_text", "")).strip()
        if q_text and q_text != "nan":
            ca = str(row.get("choice_a", "")).strip()
            cb = str(row.get("choice_b", "")).strip()
            cc = str(row.get("choice_c", "")).strip()
            cd = str(row.get("choice_d", "")).strip()
            ans = str(row.get("correct_ans", "")).strip()

            cur.execute("""
            INSERT INTO questions (term_id, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (term_id, q_text, ca, cb, cc, cd, ans))
            q_id = cur.lastrowid

            # 文系解説テーブル
            exp_b = str(row.get("exp_beginner_final", "")).strip()
            if exp_b and exp_b != "nan":
                cur.execute("INSERT INTO question_explanations_beginner (question_id, explanation) VALUES (?, ?)", (q_id, exp_b))

            # 情報科学科解説テーブル
            exp_a = str(row.get("exp_advanced_final", "")).strip()
            if exp_a and exp_a != "nan":
                cur.execute("INSERT INTO question_explanations_advanced (question_id, explanation) VALUES (?, ?)", (q_id, exp_a))

    conn.commit()
    conn.close()
    print("✅ 全テーブル（比喩・実例・文系解説・情報系解説）を完全分離した正規化DBを作成しました！")

if __name__ == "__main__":
    make_database()