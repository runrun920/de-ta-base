import sqlite3
import os
import shutil

db_file = "fe_study.db"
backup_file = "fe_study_before_migration.db"

if not os.path.exists(db_file):
    print(f"❌ {db_file} が見つかりません。")
    exit(1)

# 1. 実行前バックアップ（上書き保存）
shutil.copyfile(db_file, backup_file)
print(f"🛡️ 安全バックアップを作成しました: {backup_file}")

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# マイグレーション作業中は一時的に外部キー制約をOFFにする
cursor.execute("PRAGMA foreign_keys = OFF;")

print("🔧 1. 新スキーマ（正規化テーブル）の作成準備中...")

# 古いテーブルや中間テーブル、VIEWを整理
cursor.execute("DROP VIEW IF EXISTS terms_master;")
cursor.execute("DROP TABLE IF EXISTS new_terms;")
cursor.execute("DROP TABLE IF EXISTS question_explanations;")
cursor.execute("DROP TABLE IF EXISTS question_explanations_beginner;")
cursor.execute("DROP TABLE IF EXISTS question_explanations_advanced;")
cursor.execute("DROP TABLE IF EXISTS questions;")

# 新 terms テーブル（問題・解説カラムを除去した用語マスター）
cursor.execute("""
CREATE TABLE new_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_name TEXT UNIQUE NOT NULL,
    category TEXT,
    sub_category TEXT,
    official_def TEXT,
    url TEXT,
    intuitive_def TEXT,
    practical_example TEXT
);
""")

# questions テーブル（1用語に対して複数問題を持てる1:N設計）
cursor.execute("""
CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id INTEGER NOT NULL,
    question_type TEXT DEFAULT '正当選択',
    question_text TEXT NOT NULL,
    choice_a TEXT,
    choice_b TEXT,
    choice_c TEXT,
    choice_d TEXT,
    correct_ans TEXT,
    FOREIGN KEY (term_id) REFERENCES new_terms(id) ON DELETE CASCADE
);
""")

# question_explanations テーブル（1問に対して初学者向け・理系向け解説）
cursor.execute("""
CREATE TABLE question_explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER UNIQUE NOT NULL,
    exp_beginner TEXT,
    exp_advanced TEXT,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);
""")

print("📦 2. 既存の terms からデータを移行中...")

# 既存 terms のカラム確認
cursor.execute("PRAGMA table_info(terms);")
old_cols = [c[1] for c in cursor.fetchall()]

int_col = "intuitive_def_final" if "intuitive_def_final" in old_cols else ("intuitive_def" if "intuitive_def" in old_cols else "NULL")
prac_col = "practical_example_final" if "practical_example_final" in old_cols else ("practical_example" if "practical_example" in old_cols else "NULL")
exp_beg_col = "exp_beginner_final" if "exp_beginner_final" in old_cols else ("exp_beginner" if "exp_beginner" in old_cols else "NULL")
exp_adv_col = "exp_advanced_final" if "exp_advanced_final" in old_cols else ("exp_advanced" if "exp_advanced" in old_cols else "NULL")

# ① new_terms への移行（全用語マスター）
sql_terms = f"""
INSERT INTO new_terms (id, term_name, category, sub_category, official_def, url, intuitive_def, practical_example)
SELECT id, term_name, category, sub_category, official_def, url, {int_col}, {prac_col}
FROM terms;
"""
cursor.execute(sql_terms)
print(f"   ✅ new_terms: {cursor.rowcount} 件の用語マスターを移行しました。")

# ② questions への移行（問題文が入っている有効レコードのみ）
sql_questions = """
INSERT INTO questions (term_id, question_type, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans)
SELECT id, '正当選択', question_text, choice_a, choice_b, choice_c, choice_d, correct_ans
FROM terms
WHERE question_text IS NOT NULL AND trim(question_text) != '' AND question_text != 'nan';
"""
cursor.execute(sql_questions)
migrated_q_count = cursor.rowcount
print(f"   ✅ questions: {migrated_q_count} 件の問題を移行しました。")

# ③ question_explanations への移行（新しく振られた questions.id と紐づけ）
sql_exp = f"""
INSERT INTO question_explanations (question_id, exp_beginner, exp_advanced)
SELECT q.id, t.{exp_beg_col}, t.{exp_adv_col}
FROM questions q
JOIN terms t ON q.term_id = t.id;
"""
cursor.execute(sql_exp)
print(f"   ✅ question_explanations: {cursor.rowcount} 件の二層解説を移行しました。")

# 3. テーブルの安全差し替え
print("🔄 3. テーブルの置換とインデックス作成中...")
cursor.execute("DROP TABLE IF EXISTS terms_old;")
cursor.execute("ALTER TABLE terms RENAME TO terms_old;")
cursor.execute("ALTER TABLE new_terms RENAME TO terms;")

# 検索最適化用のインデックス
cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_term_id ON questions(term_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_explanations_qid ON question_explanations(question_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_subcat ON terms(sub_category);")

# ④ 互換ビュー（VIEW terms_master）の定義
cursor.execute("""
CREATE VIEW terms_master AS
SELECT 
    t.id AS term_id,
    q.id AS id,
    q.id AS question_id,
    t.term_name,
    t.category,
    t.sub_category,
    t.official_def,
    t.url,
    t.intuitive_def,
    t.practical_example,
    q.question_type,
    q.question_text,
    q.choice_a,
    q.choice_b,
    q.choice_c,
    q.choice_d,
    q.correct_ans,
    e.exp_beginner AS exp_beginner_final,
    e.exp_advanced AS exp_advanced_final,
    e.exp_beginner,
    e.exp_advanced
FROM terms t
LEFT JOIN questions q ON t.id = q.term_id
LEFT JOIN question_explanations e ON q.id = e.question_id;
""")
print("   ✅ 互換ビュー「terms_master」を定義しました。")

conn.commit()

# 外部キー整合性チェック
cursor.execute("PRAGMA foreign_key_check;")
errors = cursor.fetchall()
if errors:
    print(f"⚠️ 外部キー整合性エラーが検出されました: {errors}")
else:
    print("   ✅ 外部キー整合性チェック: 正常（エラーなし）")

# 外部キー制約をONに戻す
cursor.execute("PRAGMA foreign_keys = ON;")

conn.close()

print("\n" + "=" * 60)
print("🎉 データベース正規化マイグレーションが完了しました！")
print("=" * 60)
