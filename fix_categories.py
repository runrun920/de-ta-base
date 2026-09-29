import sqlite3
import csv
import re
import os

CSV_FILE = "kakomon_real_terms_urls.csv"

# IPA公式 23中分類マスター
CHUBUNRUI_MAP = {
    1: ("テクノロジ系", "1. 基礎理論"),
    2: ("テクノロジ系", "2. アルゴリズムとプログラミング"),
    3: ("テクノロジ系", "3. コンピュータ構成要素"),
    4: ("テクノロジ系", "4. システム構成要素"),
    5: ("テクノロジ系", "5. ソフトウェア"),
    6: ("テクノロジ系", "6. ハードウェア"),
    7: ("テクノロジ系", "7. ユーザーインタフェース"),
    8: ("テクノロジ系", "8. 情報メディア"),
    9: ("テクノロジ系", "9. データベース"),
    10: ("テクノロジ系", "10. ネットワーク"),
    11: ("テクノロジ系", "11. セキュリティ"),
    12: ("テクノロジ系", "12. システム開発技術"),
    13: ("テクノロジ系", "13. ソフトウェア開発管理技術"),
    14: ("マネジメント系", "14. プロジェクトマネジメント"),
    15: ("マネジメント系", "15. サービスマネジメント"),
    16: ("マネジメント系", "16. システム監査"),
    17: ("ストラテジ系", "17. システム戦略"),
    18: ("ストラテジ系", "18. システム企画"),
    19: ("ストラテジ系", "19. 経営戦略マネジメント"),
    20: ("ストラテジ系", "20. 技術戦略マネジメント"),
    21: ("ストラテジ系", "21. ビジネスインダストリ"),
    22: ("ストラテジ系", "22. 企業活動"),
    23: ("ストラテジ系", "23. 法務")
}

def clean_term(text):
    return re.sub(r'[\(（].*?[\)）]', '', text).strip()

def fix_categories_from_csv():
    if not os.path.exists(CSV_FILE):
        print(f"❌ '{CSV_FILE}' が見つかりません。")
        return

    conn = sqlite3.connect("fe_study.db")
    cur = conn.cursor()

    # 1. テーブルの初期化
    cur.execute("""
    CREATE TABLE IF NOT EXISTS term_categories (
        term_name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_category TEXT NOT NULL,
        PRIMARY KEY (term_name, sub_category)
    )
    """)
    cur.execute("DELETE FROM term_categories")
    conn.commit()

    # DB内の登録用語名一覧
    cur.execute("SELECT term_name FROM terms")
    existing_terms = set(row[0] for row in cur.fetchall())
    clean_to_raw = {clean_term(t): t for t in existing_terms}

    print(f"=== 手元の '{CSV_FILE}' から正確な中分類IDを解析中... ===")

    records = set()
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 2:
                continue
            term_name_csv = row[0].strip()
            url = row[1].strip()

            # URLから中分類番号 (/keyword/10/ や /keyword/1/ 等) を抽出
            # 例: https://www.fe-siken.com/keyword/10/10-1/ など
            m = re.search(r'/keyword/(\d+)/', url)
            if not m:
                continue

            chu_id = int(m.group(1))
            if chu_id not in CHUBUNRUI_MAP:
                continue

            cat_name, sub_name = CHUBUNRUI_MAP[chu_id]

            # DBに存在する正式な単語名と照合
            matched_name = None
            if term_name_csv in existing_terms:
                matched_name = term_name_csv
            else:
                c_name = clean_term(term_name_csv)
                if c_name in clean_to_raw:
                    matched_name = clean_to_raw[c_name]

            if matched_name:
                records.add((matched_name, cat_name, sub_name))

    print(f"   -> 照合成功: {len(records)} 件の所属データを検出しました。")

    # 2. term_categories に保存
    cur.executemany("""
    INSERT OR IGNORE INTO term_categories (term_name, category, sub_category)
    VALUES (?, ?, ?)
    """, list(records))

    # terms テーブルの基本分類も更新
    for t_name, cat, sub in records:
        cur.execute("UPDATE terms SET category = ?, sub_category = ? WHERE term_name = ?", (cat, sub, t_name))

    conn.commit()

    # 3. 集計結果の表示
    print("\n📊 【過去問道場と一致した各中分類の登録語数】:")
    for chu_id in range(1, 24):
        _, sub_name = CHUBUNRUI_MAP[chu_id]
        cur.execute("SELECT count(*) FROM term_categories WHERE sub_category = ?", (sub_name,))
        cnt = cur.fetchone()[0]
        print(f"[{chu_id:2d}/23] {sub_name:<20} : {cnt:3d} 語")

    conn.close()
    print("\n🎉 分類マッピングが完了しました！")

if __name__ == "__main__":
    fix_categories_from_csv()