# fe_study_master_23sheets.xlsx 内の「全用語一覧」および「全23中分類シート」を対象に、
# 問題文・選択肢・正解記号・解説の列のみを空（None）にして初期化する安全なクリアプログラム

import os
import shutil
import pandas as pd

XLSX_FILE = "fe_study_master_23sheets.xlsx"
BACKUP_FILE = "fe_study_master_23sheets_backup.xlsx"

# クリア対象の列（問題・選択肢・正解・解説関連）
COLUMNS_TO_CLEAR = [
    "question_text",
    "choice_a",
    "choice_b",
    "choice_c",
    "choice_d",
    "correct_ans",
    "exp_beginner_gpt",
    "exp_beginner_gemini",
    "exp_beginner_final",
    "exp_advanced_gpt",
    "exp_advanced_gemini",
    "exp_advanced_final"
]

def main():
    if not os.path.exists(XLSX_FILE):
        print(f"❌ エラー: {XLSX_FILE} が見つかりません。")
        return

    # 1. 安全のため自動バックアップを作成
    print(f"1. バックアップを作成中: {BACKUP_FILE}")
    shutil.copyfile(XLSX_FILE, BACKUP_FILE)
    print("   ✅ バックアップ作成完了")

    # 2. 全シートを読み込んで対象列のみを None (空) に置き換え
    print(f"2. {XLSX_FILE} 内の全シートを読み込み、対象列を初期化中...")
    excel = pd.ExcelFile(XLSX_FILE)
    sheet_names = excel.sheet_names
    cleaned_sheets = {}

    for s_name in sheet_names:
        df = pd.read_excel(XLSX_FILE, sheet_name=s_name)
        for col in COLUMNS_TO_CLEAR:
            if col in df.columns:
                df[col] = None
        cleaned_sheets[s_name] = df
        print(f"   - シート処理完了: {s_name}")

    # 3. Excelファイルへ書き戻し
    print(f"3. 初期化後のデータを {XLSX_FILE} に保存中...")
    with pd.ExcelWriter(XLSX_FILE, engine="openpyxl") as writer:
        for s_name, df in cleaned_sheets.items():
            df.to_excel(writer, sheet_name=s_name, index=False)

    print("-" * 50)
    print("✅ 完了しました！")
    print("   ・例え話や実用例（intuitive_def, practical_example）は保持されています。")
    print("   ・問題文・選択肢・解説列のみが空になり、再生成の準備が整いました。")
    print(f"   ・何かあった場合は {BACKUP_FILE} から復元できます。")
    print("-" * 50)

if __name__ == "__main__":
    main()