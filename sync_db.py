# 一度作ったデータベース（fe_study.db）を初期化（DROP）せず、既存のログや学習者データを守りながら、新データだけを追加・更新するプログラム
# 本番・データ追記用の「差分同期（壊さない）」用

import sqlite3
import pandas as pd
import os

CSV_FILE = "fe_study_master.csv"
XLSX_FILE = "fe_study_master_23sheets.xlsx"
DB_FILE = "fe_study.db"

def sync_database():
    # 1. データの読み込み
    if os.path.exists(XLSX_FILE):
        print(f"1. {XLSX_FILE} から最新データを読み込み中...")
        excel = pd.ExcelFile(XLSX_FILE)
        dfs = [pd.read_excel(XLSX_FILE, sheet_name=s) for s in excel.sheet_names if s != "全用語一覧"]
        df = pd.concat(dfs, ignore_index=True)
    elif os.path.exists(CSV_FILE):
        print(f"1. {CSV_FILE} から最新データを読み込み中...")
        df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")
    else:
        print("エラー: ソースファイルが見つかりません。")
        return

    print(f"2. 既存の {DB_FILE} を保持したまま、差分同期（UPSERT）を開始します...")
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # テーブルが存在しない場合のみ作成（DROPは絶対にしない）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT UNIQUE,
        category TEXT,
        sub_category TEXT,
        official_def TEXT,
        url TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS term_metaphors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        metaphor_text TEXT,
        source_ai TEXT,
        UNIQUE(term_id, source_ai),
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS term_examples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        example_text TEXT,
        source_ai TEXT,
        UNIQUE(term_id, source_ai),
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        question_text TEXT UNIQUE,
        choice_a TEXT,
        choice_b TEXT,
        choice_c TEXT,
        choice_d TEXT,
        correct_ans TEXT,
        FOREIGN KEY (term_id) REFERENCES terms(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS question_explanations_beginner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER UNIQUE,
        explanation TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS question_explanations_advanced (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER UNIQUE,
        explanation TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS term_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT,
        category TEXT,
        sub_category TEXT
    )
    """)

    # ビューの再作成（定義更新のため）
    cur.execute("DROP VIEW IF EXISTS terms_master")
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

    added_terms = 0
    updated_terms = 0
    added_questions = 0

    # 差分同期ループ
    for _, row in df.iterrows():
        t_name = str(row.get("term_name", "")).strip()
        if not t_name or t_name == "nan":
            continue

        cat = str(row.get("category", "")).strip()
        sub_cat = str(row.get("sub_category", "")).strip()
        off_def = str(row.get("kakomon_official_def", "")).strip()
        url = str(row.get("kakomon_url", "")).strip()

        # 1. 用語マスター（新規追加または更新）
        cur.execute("SELECT id FROM terms WHERE term_name = ?", (t_name,))
        res = cur.fetchone()
        if res:
            term_id = res[0]
            cur.execute("""
            UPDATE terms SET category=?, sub_category=?, official_def=?, url=?
            WHERE id=?
            """, (cat, sub_cat, off_def, url, term_id))
            updated_terms += 1
        else:
            cur.execute("""
            INSERT INTO terms (term_name, category, sub_category, official_def, url)
            VALUES (?, ?, ?, ?, ?)
            """, (t_name, cat, sub_cat, off_def, url))
            term_id = cur.lastrowid
            added_terms += 1

        # 2. 比喩
        int_f = str(row.get("intuitive_def_final", "")).strip()
        if int_f and int_f != "nan":
            cur.execute("SELECT id FROM term_metaphors WHERE term_id=? AND source_ai='Final'", (term_id,))
            m_res = cur.fetchone()
            if m_res:
                cur.execute("UPDATE term_metaphors SET metaphor_text=? WHERE id=?", (int_f, m_res[0]))
            else:
                cur.execute("INSERT INTO term_metaphors (term_id, metaphor_text, source_ai) VALUES (?, ?, 'Final')", (term_id, int_f))

        # 3. 実用例
        prac_f = str(row.get("practical_example_final", "")).strip()
        if prac_f and prac_f != "nan":
            cur.execute("SELECT id FROM term_examples WHERE term_id=? AND source_ai='Final'", (term_id,))
            e_res = cur.fetchone()
            if e_res:
                cur.execute("UPDATE term_examples SET example_text=? WHERE id=?", (prac_f, e_res[0]))
            else:
                cur.execute("INSERT INTO term_examples (term_id, example_text, source_ai) VALUES (?, ?, 'Final')", (term_id, prac_f))

        # 4. 問題
        q_text = str(row.get("question_text", "")).strip()
        if q_text and q_text != "nan":
            ca = str(row.get("choice_a", "")).strip()
            cb = str(row.get("choice_b", "")).strip()
            cc = str(row.get("choice_c", "")).strip()
            cd = str(row.get("choice_d", "")).strip()
            ans = str(row.get("correct_ans", "")).strip()

            cur.execute("SELECT id FROM questions WHERE question_text = ?", (q_text,))
            q_res = cur.fetchone()
            if q_res:
                q_id = q_res[0]
                cur.execute("""
                UPDATE questions SET choice_a=?, choice_b=?, choice_c=?, choice_d=?, correct_ans=?
                WHERE id=?
                """, (ca, cb, cc, cd, ans, q_id))
            else:
                cur.execute("""
                INSERT INTO questions (term_id, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (term_id, q_text, ca, cb, cc, cd, ans))
                q_id = cur.lastrowid
                added_questions += 1

            # 文系解説
            exp_b = str(row.get("exp_beginner_final", "")).strip()
            if exp_b and exp_b != "nan":
                cur.execute("SELECT id FROM question_explanations_beginner WHERE question_id = ?", (q_id,))
                qb_res = cur.fetchone()
                if qb_res:
                    cur.execute("UPDATE question_explanations_beginner SET explanation=? WHERE id=?", (exp_b, qb_res[0]))
                else:
                    cur.execute("INSERT INTO question_explanations_beginner (question_id, explanation) VALUES (?, ?)", (q_id, exp_b))

            # 情報科学科解説
            exp_a = str(row.get("exp_advanced_final", "")).strip()
            if exp_a and exp_a != "nan":
                cur.execute("SELECT id FROM question_explanations_advanced WHERE question_id = ?", (q_id,))
                qa_res = cur.fetchone()
                if qa_res:
                    cur.execute("UPDATE question_explanations_advanced SET explanation=? WHERE id=?", (exp_a, qa_res[0]))
                else:
                    cur.execute("INSERT INTO question_explanations_advanced (question_id, explanation) VALUES (?, ?)", (q_id, exp_a))

    conn.commit()
    conn.close()

    print("-" * 50)
    print(f"✅ 同期完了！")
    print(f"   - 新規用語追加: {added_terms} 件 / 更新: {updated_terms} 件")
    print(f"   - 新規問題追加: {added_questions} 件")
    print(f"   - 解答ログ (quiz_logs) や 閲覧ログ (term_logs) は一切壊れていません。")
    print("-" * 50)

if __name__ == "__main__":
    sync_database()