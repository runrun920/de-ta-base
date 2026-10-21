import os
import sys
import sqlite3
import pandas as pd
import openpyxl

MASTER_FILE = "fe_study_master_23sheets.xlsx"
DB_FILE = "fe_study.db"

if not os.path.exists(MASTER_FILE):
    print(f"❌ エクセルファイルが見つかりません: {MASTER_FILE}")
    sys.exit(1)

if not os.path.exists(DB_FILE):
    print(f"❌ データベースファイルが見つかりません: {DB_FILE}")
    sys.exit(1)

# --- 1. 同期前のDB状態を記録（差分集計用） ---
conn_pre = sqlite3.connect(DB_FILE)
cur_pre = conn_pre.cursor()

# 既存の (term_id, question_type) ペアをセット化
cur_pre.execute("SELECT term_id, question_type FROM questions;")
pre_existing_q = set(cur_pre.fetchall())
pre_total_q_count = len(pre_existing_q)
conn_pre.close()

print(f"1. 📖 {MASTER_FILE} から最新データを読み込み中...")
excel_file = pd.ExcelFile(MASTER_FILE)
all_sheets = excel_file.sheet_names
print(f"   検出シート数: {len(all_sheets)} シート")

# 読み取り対象カラム定義
TERM_COLS = [
    "category", "sub_category", "official_def", "url", 
    "intuitive_def_final", "practical_example_final"
]

Q1_COLS = [
    "question_text", "choice_a", "choice_b", "choice_c", "choice_d", "correct_ans",
    "exp_beginner_final", "exp_advanced_final"
]

Q2_COLS = [
    "q2_question_text", "q2_choice_a", "q2_choice_b", "q2_choice_c", "q2_choice_d", "q2_correct_ans",
    "q2_exp_beginner_final", "q2_exp_advanced_final"
]

ALL_READ_COLS = TERM_COLS + Q1_COLS + Q2_COLS

merged_data = {}

def clean_val(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return None if s in ["", "nan", "None"] else s

# ① 「全用語一覧」ベース読み込み
if "全用語一覧" in all_sheets:
    df_all = pd.read_excel(MASTER_FILE, sheet_name="全用語一覧")
    if "term_name" in df_all.columns:
        for _, row in df_all.iterrows():
            t_name = clean_val(row.get("term_name"))
            if not t_name:
                continue
            item = {"term_name": t_name}
            for col in ALL_READ_COLS:
                item[col] = clean_val(row.get(col))
            merged_data[t_name] = item

# ② 23個別シートから最新データをマージ
for s_name in all_sheets:
    if s_name in ["全用語一覧", "サマリー＆ガイドライン"]:
        continue
    
    df_sub = pd.read_excel(MASTER_FILE, sheet_name=s_name)
    if "term_name" not in df_sub.columns:
        continue
        
    for _, row in df_sub.iterrows():
        t_name = clean_val(row.get("term_name"))
        if not t_name:
            continue
            
        if t_name not in merged_data:
            merged_data[t_name] = {"term_name": t_name}
            for col in ALL_READ_COLS:
                merged_data[t_name][col] = None

        for col in ALL_READ_COLS:
            val = clean_val(row.get(col))
            if val is not None:
                merged_data[t_name][col] = val

print(f"   統合完了: 合計 {len(merged_data)} 件の用語データを検出しました。")

# --- 2. 正規化DBへのUPSERT同期 ---
print(f"2. 🔄 {DB_FILE} への同期（正規化UPSERT）を開始します...")
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

term_update_count = 0
term_insert_count = 0

for t_name, data in merged_data.items():
    # 2-1. terms テーブルの同期
    cursor.execute("SELECT id FROM terms WHERE term_name = ?;", (t_name,))
    row = cursor.fetchone()
    
    cat = data.get("category")
    subcat = data.get("sub_category")
    off_def = data.get("official_def")
    url = data.get("url")
    int_def = data.get("intuitive_def_final")
    prac_ex = data.get("practical_example_final")
    
    if row:
        term_id = row[0]
        cursor.execute("""
            UPDATE terms SET 
                category = COALESCE(?, category),
                sub_category = COALESCE(?, sub_category),
                official_def = COALESCE(?, official_def),
                url = COALESCE(?, url),
                intuitive_def = COALESCE(?, intuitive_def),
                practical_example = COALESCE(?, practical_example)
            WHERE id = ?;
        """, (cat, subcat, off_def, url, int_def, prac_ex, term_id))
        term_update_count += 1
    else:
        cursor.execute("""
            INSERT INTO terms (term_name, category, sub_category, official_def, url, intuitive_def, practical_example)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (t_name, cat, subcat, off_def, url, int_def, prac_ex))
        term_id = cursor.lastrowid
        term_insert_count += 1

    # 2-2. Q1（正当選択）の同期
    q1_text = data.get("question_text")
    if q1_text:
        cursor.execute("SELECT id FROM questions WHERE term_id = ? AND question_type = '正当選択';", (term_id,))
        q1_row = cursor.fetchone()
        
        c_a, c_b, c_c, c_d = data.get("choice_a"), data.get("choice_b"), data.get("choice_c"), data.get("choice_d")
        ans = data.get("correct_ans")
        exp_b = data.get("exp_beginner_final")
        exp_a = data.get("exp_advanced_final")
        
        if q1_row:
            qid = q1_row[0]
            cursor.execute("""
                UPDATE questions SET 
                    question_text = ?, choice_a = ?, choice_b = ?, choice_c = ?, choice_d = ?, correct_ans = ?
                WHERE id = ?;
            """, (q1_text, c_a, c_b, c_c, c_d, ans, qid))
            cursor.execute("""
                INSERT INTO question_explanations (question_id, exp_beginner, exp_advanced)
                VALUES (?, ?, ?)
                ON CONFLICT(question_id) DO UPDATE SET 
                    exp_beginner = excluded.exp_beginner, 
                    exp_advanced = excluded.exp_advanced;
            """, (qid, exp_b, exp_a))
        else:
            cursor.execute("""
                INSERT INTO questions (term_id, question_type, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans)
                VALUES (?, '正当選択', ?, ?, ?, ?, ?, ?);
            """, (term_id, q1_text, c_a, c_b, c_c, c_d, ans))
            qid = cursor.lastrowid
            cursor.execute("""
                INSERT INTO question_explanations (question_id, exp_beginner, exp_advanced)
                VALUES (?, ?, ?);
            """, (qid, exp_b, exp_a))

    # 2-3. Q2（不適当選択）の同期
    q2_text = data.get("q2_question_text")
    if q2_text:
        cursor.execute("SELECT id FROM questions WHERE term_id = ? AND question_type = '不適当選択';", (term_id,))
        q2_row = cursor.fetchone()
        
        c2_a, c2_b, c2_c, c2_d = data.get("q2_choice_a"), data.get("q2_choice_b"), data.get("q2_choice_c"), data.get("q2_choice_d")
        ans2 = data.get("q2_correct_ans")
        exp2_b = data.get("q2_exp_beginner_final")
        exp2_a = data.get("q2_exp_advanced_final")
        
        if q2_row:
            q2id = q2_row[0]
            cursor.execute("""
                UPDATE questions SET 
                    question_text = ?, choice_a = ?, choice_b = ?, choice_c = ?, choice_d = ?, correct_ans = ?
                WHERE id = ?;
            """, (q2_text, c2_a, c2_b, c2_c, c2_d, ans2, q2id))
            cursor.execute("""
                INSERT INTO question_explanations (question_id, exp_beginner, exp_advanced)
                VALUES (?, ?, ?)
                ON CONFLICT(question_id) DO UPDATE SET 
                    exp_beginner = excluded.exp_beginner, 
                    exp_advanced = excluded.exp_advanced;
            """, (q2id, exp2_b, exp2_a))
        else:
            cursor.execute("""
                INSERT INTO questions (term_id, question_type, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans)
                VALUES (?, '不適当選択', ?, ?, ?, ?, ?, ?);
            """, (term_id, q2_text, c2_a, c2_b, c2_c, c2_d, ans2))
            q2id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO question_explanations (question_id, exp_beginner, exp_advanced)
                VALUES (?, ?, ?);
            """, (q2id, exp2_b, exp2_a))

conn.commit()

# --- 3. 差分と内訳の集計 ---
cursor.execute("SELECT q.term_id, q.question_type, t.sub_category FROM questions q JOIN terms t ON q.term_id = t.id;")
post_q_records = cursor.fetchall()
post_total_q_count = len(post_q_records)

newly_added_count = 0
newly_by_cat = {}

for term_id, qtype, subcat in post_q_records:
    if (term_id, qtype) not in pre_existing_q:
        newly_added_count += 1
        key = f"{subcat} ({qtype})"
        newly_by_cat[key] = newly_by_cat.get(key, 0) + 1

# Q1/Q2それぞれの総数
cursor.execute("SELECT count(*) FROM questions WHERE question_type = '正当選択';")
total_q1 = cursor.fetchone()[0]
cursor.execute("SELECT count(*) FROM questions WHERE question_type = '不適当選択';")
total_q2 = cursor.fetchone()[0]

conn.close()

print("-" * 65)
print(f"✅ 同期完了！")
print(f"   - 用語マスター更新: {term_update_count} 件 （新規追加: {term_insert_count} 件）")
print(f"   - 💡 今回新しくDBへ登録された問題: 【 {newly_added_count} 件 】")
print(f"   - 📊 DB内問題総数: {post_total_q_count} 件 (正当選択: {total_q1} 件 / 不適当選択: {total_q2} 件)")

if newly_added_count > 0:
    print("\n   [今回追加された問題の内訳]")
    for cat_name, cnt in sorted(newly_by_cat.items()):
        print(f"     * {cat_name}: +{cnt} 件")

print(f"\n   - 解答ログ (quiz_logs) や 閲覧ログ (term_logs) は一切壊れていません。")
print("-" * 65)

print("\n🚀 【GitHub更新コマンド】次の3行をターミナルで実行してください:")
print("git add -A")
print(f'git commit -m "{post_total_q_count}問 (Q1:{total_q1}, Q2:{total_q2}) 同期完了"')
print("git pull --rebase origin main && git push origin main\n")
