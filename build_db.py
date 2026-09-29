import sqlite3
import pandas as pd
import os

CSV_FILE = "fe_study_master.csv"
DB_FILE = "fe_study.db"

def make_database():
    if not os.path.exists(CSV_FILE):
        print(f"エラー: {CSV_FILE} が見つかりません。")
        return

    print(f"1. {CSV_FILE} を読み込み中...")
    df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")

    print(f"2. データベース（{DB_FILE}）を作成中...")
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # 辞書用 terms テーブル
    cur.execute("DROP TABLE IF EXISTS terms")
    cur.execute("""
    CREATE TABLE terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT,
        category TEXT,
        sub_category TEXT,
        official_def TEXT,
        url TEXT
    )
    """)

    # 演習・特製解説用 terms_master テーブル
    cur.execute("DROP TABLE IF EXISTS terms_master")
    cur.execute("""
    CREATE TABLE terms_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT,
        category TEXT,
        sub_category TEXT,
        official_def TEXT,
        intuitive_def TEXT,
        practical_example TEXT,
        question_text TEXT,
        choice_a TEXT,
        choice_b TEXT,
        choice_c TEXT,
        choice_d TEXT,
        correct_ans TEXT,
        explanation_beginner TEXT,
        explanation_advanced TEXT
    )
    """)

    # 分類絞り込み用 term_categories テーブル
    cur.execute("DROP TABLE IF EXISTS term_categories")
    cur.execute("""
    CREATE TABLE term_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_name TEXT,
        category TEXT,
        sub_category TEXT
    )
    """)

    # データの流し込み
    for _, row in df.iterrows():
        t_name = str(row.get("term_name", "")).strip()
        cat = str(row.get("category", "")).strip()
        sub_cat = str(row.get("sub_category", "")).strip()
        off_def = str(row.get("kakomon_official_def", "")).strip()
        url = str(row.get("kakomon_url", "")).strip()

        if not t_name or t_name == "nan":
            continue

        # terms へ登録
        cur.execute("INSERT INTO terms (term_name, category, sub_category, official_def, url) VALUES (?, ?, ?, ?, ?)",
                    (t_name, cat, sub_cat, off_def, url))
        
        # カテゴリテーブルへ登録
        cur.execute("INSERT INTO term_categories (term_name, category, sub_category) VALUES (?, ?, ?)",
                    (t_name, cat, sub_cat))

        # 例え話や問題が入っているものは terms_master にも登録
        int_final = str(row.get("intuitive_def_final", "")).strip()
        prac_final = str(row.get("practical_example_final", "")).strip()
        q_text = str(row.get("question_text", "")).strip()

        if (int_final and int_final != "nan") or (q_text and q_text != "nan"):
            cur.execute("""
            INSERT INTO terms_master (
                term_name, category, sub_category, official_def,
                intuitive_def, practical_example,
                question_text, choice_a, choice_b, choice_c, choice_d, correct_ans,
                explanation_beginner, explanation_advanced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t_name, cat, sub_cat, off_def,
                int_final if int_final != "nan" else "",
                prac_final if prac_final != "nan" else "",
                q_text if q_text != "nan" else "",
                str(row.get("choice_a", "")).strip(),
                str(row.get("choice_b", "")).strip(),
                str(row.get("choice_c", "")).strip(),
                str(row.get("choice_d", "")).strip(),
                str(row.get("correct_ans", "")).strip(),
                str(row.get("exp_beginner_final", "")).strip(),
                str(row.get("exp_advanced_final", "")).strip()
            ))

    conn.commit()
    conn.close()
    print("✅ データベース（fe_study.db）の作成が完了しました！")

if __name__ == "__main__":
    make_database()
