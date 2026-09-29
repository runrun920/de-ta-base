# （fe_study.db）にすでに保存されている 3,300語以上の公式定義・URL・シラバス分類 をベースに、
# 『直感的理解.xlsx』の各シート（ChatGPT・Geminiの例え話や実用例）を自動突合・統合して、
# 新しいマスターファイル（fe_study_master.xlsx）を出力する統合プログラム

import sqlite3
import openpyxl
import pandas as pd
import csv
import re
import os

DB_FILE = "fe_study.db"
INTUITIVE_FILE = "直感的理解.xlsx"
URL_CSV_FILE = "kakomon_real_terms_urls.csv"
OUTPUT_XLSX = "fe_study_master.xlsx"
OUTPUT_CSV = "fe_study_master.csv"

# IPA公式 23中分類の正規順序
SUB_CAT_ORDER = [
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
    "13. ソフトウェア開発管理技術",
    "14. プロジェクトマネジメント",
    "15. サービスマネジメント",
    "16. システム監査",
    "17. システム戦略",
    "18. システム企画",
    "19. 経営戦略マネジメント",
    "20. 技術戦略マネジメント",
    "21. ビジネスインダストリ",
    "22. 企業活動",
    "23. 法務"
]
SUB_CAT_ORDER_MAP = {name: idx for idx, name in enumerate(SUB_CAT_ORDER)}

def clean_term(text):
    if not text:
        return ""
    t = re.sub(r'[\(（].*?[\)）]', '', str(text))
    t = re.sub(r'[a-zA-Z\s]+$', '', t)
    return t.strip()

def clean_definition_text(text):
    """HTMLスクレイピング由来の不自然な連続改行・不要な空白を除去・整形"""
    if not text:
        return ""
    t = str(text).replace('\r\n', '\n').replace('\r', '\n')
    # 連続する複数の空白を1つに
    t = re.sub(r'[ \t\u3000]+', ' ', t)
    # 3行以上の連続改行を最大1行の空行に正規化
    t = re.sub(r'\n{3,}', '\n\n', t)
    # 行頭・行末の不要な空白を除去
    lines = [line.strip() for line in t.split('\n')]
    cleaned = "\n".join(l for l in lines if l)
    return cleaned.strip()

def build_master_dataset():
    # 1. URL辞書の作成
    print(f"=== 1. '{URL_CSV_FILE}' からURL一覧を読み込み中... ===")
    url_dict = {}
    if os.path.exists(URL_CSV_FILE):
        with open(URL_CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and len(row) >= 2:
                    raw_name = row[0].strip()
                    url_val = row[1].strip()
                    url_dict[raw_name] = url_val
                    url_dict[clean_term(raw_name)] = url_val
        print(f"   -> {len(url_dict)} 件のURLマッピングをロードしました。")
    else:
        print(f"⚠️ '{URL_CSV_FILE}' が見つかりませんでした。")

    # 2. 直感的理解.xlsx を解析
    print(f"\n=== 2. 友達の作成ファイル（{INTUITIVE_FILE}）を解析中... ===")
    intuitive_data = {}
    if os.path.exists(INTUITIVE_FILE):
        wb = openpyxl.load_workbook(INTUITIVE_FILE, data_only=True)
        for sname in wb.sheetnames:
            if sname in ["コピー", "Sheet1"]:
                continue
            ws = wb[sname]
            for r in range(3, ws.max_row + 1):
                raw_term = ws.cell(row=r, column=1).value
                if not raw_term:
                    continue

                c_term = clean_term(raw_term)
                if not c_term or c_term in ["用語", "単語"]:
                    continue

                gpt_int = clean_definition_text(ws.cell(row=r, column=2).value or "")
                gpt_prac = clean_definition_text(ws.cell(row=r, column=3).value or "")
                gpt_def = clean_definition_text(ws.cell(row=r, column=4).value or "")

                gem_int = clean_definition_text(ws.cell(row=r, column=5).value or "")
                gem_prac = clean_definition_text(ws.cell(row=r, column=6).value or "")

                final_int = gem_int if gem_int else gpt_int
                final_prac = gem_prac if gem_prac else gpt_prac

                data_obj = {
                    "intuitive_def_gpt": gpt_int,
                    "intuitive_def_gemini": gem_int,
                    "intuitive_def_final": final_int,
                    "practical_example_gpt": gpt_prac,
                    "practical_example_gemini": gem_prac,
                    "practical_example_final": final_prac,
                    "sheet_official_def": gpt_def
                }
                intuitive_data[raw_term] = data_obj
                intuitive_data[c_term] = data_obj

        print(f"   -> 『{INTUITIVE_FILE}』から比喩・実例データを抽出しました。")
    else:
        print(f"⚠️ '{INTUITIVE_FILE}' が見つかりませんでした。")

    # 3. SQLiteデータベース（fe_study.db）から取得
    print(f"\n=== 3. データベース（{DB_FILE}）から用語一覧を取得中... ===")
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT id, term_name, category, sub_category, official_def FROM terms")
    db_terms = cur.fetchall()

    try:
        cur.execute("""
        SELECT term_name, question_text, choice_a, choice_b, choice_c, choice_d, 
               correct_ans, explanation_beginner, explanation_advanced 
        FROM terms_master
        """)
        master_q_data = {r[0]: r[1:] for r in cur.fetchall()}
    except Exception:
        master_q_data = {}

    conn.close()
    print(f"   -> DBから {len(db_terms)} 語の基本データをロードしました。")

    # 4. データの突合・統合
    print("\n=== 4. データを突合・クレンジング中... ===")
    master_rows = []
    matched_count = 0

    for row in db_terms:
        t_id, t_name, cat, sub_cat, off_def = row
        c_name = clean_term(t_name)

        term_url = url_dict.get(t_name) or url_dict.get(c_name) or ""

        it_info = intuitive_data.get(t_name) or intuitive_data.get(c_name) or {}
        if it_info:
            matched_count += 1

        q_info = master_q_data.get(t_name) or master_q_data.get(c_name)
        if q_info:
            q_text, ca, cb, cc, cd, ans, exp_beg, exp_adv = q_info
        else:
            q_text = ca = cb = cc = cd = ans = exp_beg = exp_adv = ""

        # 公式定義の改行クレンジング
        raw_official = off_def if off_def else it_info.get("sheet_official_def", "")
        clean_official = clean_definition_text(raw_official)

        # ソート用インデックス（未知の分類は末尾に配置）
        sort_order = SUB_CAT_ORDER_MAP.get(sub_cat, 999)

        master_rows.append({
            "_sort_key": sort_order,
            "term_name": t_name,
            "category": cat or "",
            "sub_category": sub_cat or "",
            "kakomon_official_def": clean_official,
            "kakomon_url": term_url,
            "intuitive_def_gpt": it_info.get("intuitive_def_gpt", ""),
            "intuitive_def_gemini": it_info.get("intuitive_def_gemini", ""),
            "intuitive_def_final": it_info.get("intuitive_def_final", ""),
            "practical_example_gpt": it_info.get("practical_example_gpt", ""),
            "practical_example_gemini": it_info.get("practical_example_gemini", ""),
            "practical_example_final": it_info.get("practical_example_final", ""),
            "question_text": q_text,
            "choice_a": ca,
            "choice_b": cb,
            "choice_c": cc,
            "choice_d": cd,
            "correct_ans": ans,
            "exp_beginner_gpt": exp_beg,
            "exp_beginner_gemini": "",
            "exp_beginner_final": exp_beg,
            "exp_advanced_gpt": exp_adv,
            "exp_advanced_gemini": "",
            "exp_advanced_final": exp_adv,
            "notes": "手作り比喩マッチ済み" if it_info else ""
        })

    df = pd.DataFrame(master_rows)

    # 5. sub_category（1〜23のシラバス順）および 用語名 で並び替え
    print("   -> 中分類（1. 基礎理論 〜 23. 法務）順にソート中...")
    df.sort_values(by=["_sort_key", "term_name"], inplace=True)
    df.drop(columns=["_sort_key"], inplace=True)

    # 6. 出力
    print(f"\n=== 5. ファイル出力中... ===")
    with pd.ExcelWriter(OUTPUT_XLSX, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="FE全用語マスター")
    print(f"   ✅ Excel出力完了: {OUTPUT_XLSX}")

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"   ✅ CSV出力完了: {OUTPUT_CSV}")

    print(f"\n🎉 統合・クレンジング・ソートがすべて完了しました！")
    print(f"・総登録語数: {len(df)} 語")
    print(f"・整列順序: 1. 基礎理論 ➔ 2. アルゴリズム ... ➔ 23. 法務")

if __name__ == "__main__":
    build_master_dataset()