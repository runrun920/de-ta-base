"""
不適当な選択肢を選ぶ問題を生成するプログラム
"""
# 既存のQ1データや用語マスターを絶対に上書きしない:
# すでに q2_question_text が入っている行は自動スキップ。
# 比喩（intuitive_def）や実用例（practical_example）はQ1作成時にすでにあるため、
# 無駄に再生成せずトークン消費と時間を節約。


"""
FE-AI Tutor: Q2（不適当選択問題・属性別解説）自動生成スクリプト
- 形式: 「〜に関する記述として、不適切なものはどれか」
- 保存先: fe_study_master_23sheets.xlsx の各シートの q2_... 列
"""

import os
import sys
import time
import signal
from typing import Optional
from pydantic import BaseModel, Field
import openpyxl
from google import genai
from google.genai import types

# =========================================================
# 1. 認証設定
# =========================================================
CREDENTIALS_JSON = "gcp_key.json"
PROJECT_ID = "gen-lang-client-0984224626"
LOCATION = "us-central1"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(CREDENTIALS_JSON)

# =========================================================
# 2. 実行パラメータの設定
# =========================================================
EXCEL_FILE = "fe_study_master_23sheets.xlsx"
MODEL_NAME = "gemini-2.5-flash"
SAVE_INTERVAL = 5
MAX_GENERATE_COUNT = None  # まずは5問テスト。問題なければ None に変更してください

# AIに「正解となる不適切な文を1つ」「対象用語に関する正しい説明文を3つ（ダミー）」を出力させます。
class GeneratedQ2Data(BaseModel):
    question_text: str = Field(description="基本情報技術者試験（科目A）形式の『不適切なもの・誤っているものを選べ』という4択問題文")
    
    wrong_choice: str = Field(description="【正解となる選択肢】対象用語に関する『誤った説明・不適切な記述』の文章（1文）")
    correct_fact_1: str = Field(description="【ダミー選択肢1】対象用語に関する『正しい説明・適切な事実』の文章（1文）")
    correct_fact_2: str = Field(description="【ダミー選択肢2】対象用語に関する『正しい説明・適切な事実』の文章（1文）")
    correct_fact_3: str = Field(description="【ダミー選択肢3】対象用語に関する『正しい説明・適切な事実』の文章（1文）")
    
    beg_summary: str = Field(description="初学者向け全体要約（対象用語の要点と、何が不適切とされたかの平易な解説 1〜2文）")
    beg_why_wrong: str = Field(description="選ぶべき不適切選択肢について、なぜそれが間違いなのか、本来はどういう意味かの平易な解説（1行）")
    beg_why_fact1: str = Field(description="ダミー1がなぜ用語の説明として正しいかの平易な解説（1行）")
    beg_why_fact2: str = Field(description="ダミー2がなぜ用語の説明として正しいかの平易な解説（1行）")
    beg_why_fact3: str = Field(description="ダミー3がなぜ用語の説明として正しいかの平易な解説（1行）")

    adv_summary: str = Field(description="理系向け技術要約（技術仕様や理論的背景を踏まえた要約 1〜2文）")
    adv_why_wrong: str = Field(description="不適切選択肢の技術的誤謬および本来のアルゴリズム/プロトコルの詳細（1〜2行）")
    adv_why_fact1: str = Field(description="ダミー1の技術的正当性（1〜2行）")
    adv_why_fact2: str = Field(description="ダミー2の技術的正当性（1〜2行）")
    adv_why_fact3: str = Field(description="ダミー3の技術的正当性（1〜2行）")


try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print("🔑 Google Cloud 認証に接続しました。")
except Exception as e:
    print(f"❌ 認証クライアントの初期化に失敗しました: {e}")
    sys.exit(1)

wb_global: Optional[openpyxl.Workbook] = None
pending_changes = 0

def safe_save_excel(file_path: str):
    global wb_global, pending_changes
    if wb_global and pending_changes > 0:
        print(f"\n💾 Excelファイルを保存しています ({pending_changes} 件)...")
        wb_global.save(file_path)
        pending_changes = 0
        print("✅ 保存完了")

def signal_handler(sig, frame):
    print("\n⚠️ 中断シグナルを受信しました。未保存データを安全に書き込みます...")
    safe_save_excel(EXCEL_FILE)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


def generate_q2_question(term_name: str, sub_category: str, official_def: str) -> Optional[GeneratedQ2Data]:
    system_instruction = (
        "あなたは国家試験「基本情報技術者試験（科目A）」の専門エキスパートです。\n"
        "思考プロセスや前置きは不要です。直接JSONフォーマットを出力してください。\n\n"
        "【厳格な生成ルール（不適当選択問題）】\n"
        "1. 出題形式は必ず「〜に関する記述として、不適切なものはどれか」または「誤っているものはどれか」としてください。\n"
        "2. 出題対象は必ず【対象用語】そのものにフォーカスしてください。他のシラバス用語を出題してはいけません。\n"
        "3. wrong_choice には『正解となる誤りの記述（1つ）』を出力してください。\n"
        "4. correct_fact_1〜3 には『対象用語に関する正しい説明文（3つ）』を出力してください。\n"
        "5. 選択肢文の中に記号（ア・イ・ウ・エ）や「正解：」「誤答：」などのラベルは含めないでください。"
    )

    prompt = f"""対象用語: {term_name}
中分類: {sub_category}
公式定義: {official_def if official_def else 'シラバス標準定義'}

この用語について、「不適切なものを1つ選ばせる4択問題」と、初学者向け・理系向けの二層解説パーツをJSON形式で作成してください。"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=GeneratedQ2Data,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=1100,
                temperature=0.1
            )
        )
        return response.parsed
    except Exception as e:
        print(f"\n❌ APIエラー [{term_name}]: {e}")
        return None


def main():
    global wb_global, pending_changes

    if not os.path.exists(EXCEL_FILE):
        print(f"❌ エラー: Excelファイル '{EXCEL_FILE}' が見つかりません。")
        return

    print(f"📖 {EXCEL_FILE} を読み込み中...")
    wb_global = openpyxl.load_workbook(EXCEL_FILE)
    sheets = [s for s in wb_global.sheetnames if s != "全用語一覧"]

    SYMBOL_LIST = ["ア", "イ", "ウ", "エ"]
    session_generated = 0
    all_stopped = False

    print("🚀 Q2（不適当選択問題）の生成を開始します...")

    for sheet_name in sheets:
        if all_stopped:
            break

        ws = wb_global[sheet_name]
        headers = {}
        for col in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=col).value
            if val:
                headers[str(val).strip()] = col

        # 必須の列が存在するか確認
        if "q2_question_text" not in headers:
            continue

        for row in range(2, ws.max_row + 1):
            if MAX_GENERATE_COUNT and session_generated >= MAX_GENERATE_COUNT:
                print(f"\n🏁 今回の生成上限（{MAX_GENERATE_COUNT}件）に到達したため停止します。")
                all_stopped = True
                break

            term_val = ws.cell(row=row, column=headers["term_name"]).value
            if not term_val or str(term_val).strip() in ["", "nan"]:
                continue

            term_name = str(term_val).strip()
            
            # すでにQ2が入っていればスキップ
            existing_q2 = ws.cell(row=row, column=headers["q2_question_text"]).value
            if existing_q2 and str(existing_q2).strip() not in ["", "nan"]:
                continue

            sub_cat = str(ws.cell(row=row, column=headers.get("sub_category", 1)).value or sheet_name).strip()
            off_def = str(ws.cell(row=row, column=headers.get("kakomon_official_def", 1)).value or "").strip()

            print(f"⚙️ [Q2生成] {term_name} ({sub_cat}) ...", end="", flush=True)
            start_t = time.time()

            data = generate_q2_question(term_name, sub_cat, off_def)

            if data:
                # 正解記号（不適切な文が入る位置）をア〜エでローテーション
                target_symbol = SYMBOL_LIST[session_generated % 4]
                correct_idx = SYMBOL_LIST.index(target_symbol)

                choice_texts = ["", "", "", ""]
                beg_lines = ["", "", "", ""]
                adv_lines = ["", "", "", ""]

                # 不適切な文（正解）を配置
                choice_texts[correct_idx] = data.wrong_choice
                beg_lines[correct_idx] = f"【正解（不適切）：{target_symbol}】{data.beg_why_wrong}"
                adv_lines[correct_idx] = f"【正解（不適切）：{target_symbol}】{data.adv_why_wrong}"

                # 適切な文（ダミー）を配置
                fact_texts = [data.correct_fact_1, data.correct_fact_2, data.correct_fact_3]
                fact_beg_whys = [data.beg_why_fact1, data.beg_why_fact2, data.beg_why_fact3]
                fact_adv_whys = [data.adv_why_fact1, data.adv_why_fact2, data.adv_why_fact3]

                f_idx = 0
                for i in range(4):
                    if i != correct_idx:
                        sym = SYMBOL_LIST[i]
                        choice_texts[i] = fact_texts[f_idx]
                        beg_lines[i] = f"【適切：{sym}】{fact_beg_whys[f_idx]}"
                        adv_lines[i] = f"【適切：{sym}】{fact_adv_whys[f_idx]}"
                        f_idx += 1

                exp_beg_full = (
                    f"{data.beg_summary}\n\n"
                    f"【各選択肢の解説】\n\n"
                    f"{beg_lines[0]}\n\n"
                    f"{beg_lines[1]}\n\n"
                    f"{beg_lines[2]}\n\n"
                    f"{beg_lines[3]}"
                )

                exp_adv_full = (
                    f"{data.adv_summary}\n\n"
                    f"【技術詳細と各選択肢】\n\n"
                    f"{adv_lines[0]}\n\n"
                    f"{adv_lines[1]}\n\n"
                    f"{adv_lines[2]}\n\n"
                    f"{adv_lines[3]}"
                )

                # Excelの q2_... 列へ書き込み
                ws.cell(row=row, column=headers["q2_question_text"]).value = data.question_text
                ws.cell(row=row, column=headers["q2_choice_a"]).value = choice_texts[0]
                ws.cell(row=row, column=headers["q2_choice_b"]).value = choice_texts[1]
                ws.cell(row=row, column=headers["q2_choice_c"]).value = choice_texts[2]
                ws.cell(row=row, column=headers["q2_choice_d"]).value = choice_texts[3]
                ws.cell(row=row, column=headers["q2_correct_ans"]).value = target_symbol
                ws.cell(row=row, column=headers["q2_exp_beginner_final"]).value = exp_beg_full
                ws.cell(row=row, column=headers["q2_exp_advanced_final"]).value = exp_adv_full

                elapsed = time.time() - start_t
                session_generated += 1
                pending_changes += 1
                print(f" ✅ 完了 (不適切正解:{target_symbol} ｜ {elapsed:.2f}秒)")

                if pending_changes >= SAVE_INTERVAL:
                    safe_save_excel(EXCEL_FILE)
            else:
                print(" ⚠️ スキップ")

            time.sleep(0.5)

    safe_save_excel(EXCEL_FILE)
    print(f"\n🎉 実行終了: 今回 Q2の生成 {session_generated} 件")

if __name__ == "__main__":
    main()

