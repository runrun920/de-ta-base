"""
問題文と解説が正しいか精査するプログラム
"""
import os
import sys
import time
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import pandas as pd
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

CREDENTIALS_JSON = "gcp_key.json"
PROJECT_ID = "gen-lang-client-0984224626"
LOCATION = "us-central1"
MASTER_FILE = "fe_study_master_23sheets.xlsx"
EVAL_FILE = "基本情報問題・解説_品質精査評価シート.xlsx"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(CREDENTIALS_JSON)

# マスター側のシート名（ユーザーインタフェース / 情報メディア）に対応
TARGET_MAPPING = [
    {
        "master_sheet": "7. ユーザーインタフェース", 
        "output_title_candidates": ["ユーザーインタフェース 問題精査", "ヒューマンインタフェース 問題精査"]
    },
    {
        "master_sheet": "8. 情報メディア", 
        "output_title_candidates": ["情報メディア 問題精査", "マルチメディア 問題精査"]
    }
]

HEADERS = [
    "No", "用語名", "中分類", "生成問題文",
    "選択肢ア", "選択肢イ", "選択肢ウ", "選択肢エ",
    "正解記号", "初学者向け解説", "理系向け解説",
    "【評価1】正答の妥当性", "【評価2】問題文・難易度",
    "【評価3】属性別解説の質", "【評価4】記号一致",
    "指摘事項・修正案・気づきコメント"
]

class StrictQuestionEvaluation(BaseModel):
    fact_check_correct: str = Field(description="正解選択肢の技術的正確性の検証")
    fact_check_distractors: str = Field(description="誤答選択肢の検証")
    critique_explanation: str = Field(description="初学者向けと理系向け解説の精査")
    eval1_validity: str = Field(description="1:問題なし、2:表現修正推奨、3:誤り・要差し替え のいずれか")
    eval2_difficulty: str = Field(description="○:適切、△:やや曖昧、×:不適切 のいずれか")
    eval3_explanation: str = Field(description="○:差別化十分、△:差が薄い、×:不適切 のいずれか")
    eval4_symbol: str = Field(description="○:完全一致、×:不一致 のいずれか")
    comment: str = Field(description="改善提案・具体的な指摘（60〜120文字程度）")

try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
except Exception as e:
    print(f"❌ API接続エラー: {e}")
    sys.exit(1)

print(f"📖 {MASTER_FILE} を読み込み中...")
excel_master = pd.ExcelFile(MASTER_FILE)
master_sheets = excel_master.sheet_names

wb_eval = openpyxl.load_workbook(EVAL_FILE)

header_fill = PatternFill(start_color="46538A", end_color="46538A", fill_type="solid")
header_font = Font(name="Yu Gothic", size=10, bold=True, color="FFFFFF")
body_font = Font(name="Yu Gothic", size=9)
thin_side = Side(border_style="thin", color="CCCCCC")
cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
align_left = Alignment(horizontal="left", vertical="top", wrap_text=True)

for target in TARGET_MAPPING:
    ms_name = target["master_sheet"]
    candidates = target["output_title_candidates"]

    if ms_name not in master_sheets:
        print(f"⚠️ マスターExcel内にシート「{ms_name}」が見つかりません。")
        continue

    # 出力先シート名を決定（既存の空シートを優先して探す）
    chosen_title = None
    for cand in candidates:
        if cand in wb_eval.sheetnames:
            chosen_title = cand
            break
    if not chosen_title:
        chosen_title = candidates[0]

    print(f"\n==========================================")
    print(f"🧐 厳格査読開始: {chosen_title} (元データ: {ms_name})")
    print(f"==========================================")

    df_cat = pd.read_excel(MASTER_FILE, sheet_name=ms_name)
    valid_df = df_cat[
        df_cat["question_text"].notna() & 
        (df_cat["question_text"].astype(str).str.strip() != "") &
        (df_cat["question_text"].astype(str).str.strip() != "nan")
    ].copy()

    total_valid = len(valid_df)
    print(f"📊 「{ms_name}」の登録済み問題数: {total_valid} 件")

    if total_valid == 0:
        print(f"⚠️ 「{ms_name}」には登録済み問題がありません。スキップします。")
        continue

    sample_n = min(20, total_valid)
    sampled_rows = valid_df.sample(n=sample_n, random_state=42).to_dict("records")

    # シートの初期化・作成
    if chosen_title in wb_eval.sheetnames:
        ws = wb_eval[chosen_title]
        ws.delete_rows(1, ws.max_row + 1)
    else:
        ws = wb_eval.create_sheet(title=chosen_title)

    # 1行目にヘッダーを設定
    ws.row_dimensions[1].height = 28
    for col_idx, h_text in enumerate(HEADERS, start=2):
        c = ws.cell(row=1, column=col_idx, value=h_text)
        c.fill = header_fill
        c.font = header_font
        c.alignment = align_center
        c.border = cell_border

    # 各行のAI厳格査読
    for i, row_data in enumerate(sampled_rows):
        row_num = 2 + i
        ws.row_dimensions[row_num].height = 50
        no_val = i + 1

        t_name = str(row_data.get("term_name", "")).strip()
        s_cat = str(row_data.get("sub_category", ms_name)).strip()
        q_text = str(row_data.get("question_text", "")).strip()
        ch_a = str(row_data.get("choice_a", "")).strip()
        ch_b = str(row_data.get("choice_b", "")).strip()
        ch_c = str(row_data.get("choice_c", "")).strip()
        ch_d = str(row_data.get("choice_d", "")).strip()
        c_ans = str(row_data.get("correct_ans", "")).strip()
        exp_beg = str(row_data.get("exp_beginner_final", "")).strip()
        exp_adv = str(row_data.get("exp_advanced_final", "")).strip()

        print(f"[{no_val}/{sample_n}] 厳格査読中: {t_name}...", end="", flush=True)

        eval_prompt = f"""
あなたは基本情報技術者試験（科目A）の極めて厳格な問題審査委員・技術査読者です。
受験生が不利益を被らないよう、ハルシネーション（技術的誤り）、悪問（正解が複数存在する、あるいは正解が存在しない）、
解説の不十分さを厳しく精査してください。

【対象用語】: {t_name}
【分野】: {s_cat}
【問題文】: {q_text}
【選択肢ア】: {ch_a}
【選択肢イ】: {ch_b}
【選択肢ウ】: {ch_c}
【選択肢エ】: {ch_d}
【正解記号】: {c_ans}
【初学者向け解説】: {exp_beg}
【理系向け解説】: {exp_adv}

### 厳格査読の手順と基準：
1. 正解選択肢が情報工学・IPA公式シラバスの定義として100%正しいか厳密に確認する。
2. 他の3つの誤答選択肢の中に「解釈によっては正解と言えてしまう曖昧なもの」が含まれていないか粗探しをする。
3. 初学者向け解説が単なる用語の言い換えになっていないか、理系向け解説に技術的裏付けがあるかを批判的に評価する。
4. 解説内の「正解は【〇】」という記述と【正解記号】が完全に合致しているか確認する。

### 判定ラベルの付与ルール：
- eval1_validity: 正解が唯一かつ完璧なら「1:問題なし」、わずかでも表現の曖昧さや改善点があれば「2:表現修正推奨」、明確な誤り・複数正解・正解なしなら「3:誤り・要差し替え」
- eval2_difficulty: 「○:適切」「△:やや曖昧」「×:不適切」
- eval3_explanation: 「○:差別化十分」「△:差が薄い」「×:不適切」
- eval4_symbol: 「○:完全一致」「×:不一致」
- comment: 問題の長所だけでなく、改善できる余地や懸念点を具体的に指摘する。
"""

        time.sleep(1.0)

        try:
            res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=eval_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StrictQuestionEvaluation,
                    temperature=0.2
                )
            )
            ev: StrictQuestionEvaluation = res.parsed
            e1, e2, e3, e4, comm = ev.eval1_validity, ev.eval2_difficulty, ev.eval3_explanation, ev.eval4_symbol, ev.comment
        except Exception as ex:
            print(f"\n❌ APIエラー発生 ({t_name}): {ex}")
            e1, e2, e3, e4, comm = "エラー", "エラー", "エラー", "エラー", f"APIエラー: {str(ex)[:80]}"

        row_values = [
            no_val, t_name, s_cat, q_text,
            ch_a, ch_b, ch_c, ch_d, c_ans,
            exp_beg, exp_adv,
            e1, e2, e3, e4, comm
        ]

        for col_idx, val in enumerate(row_values, start=2):
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.font = body_font
            cell.border = cell_border
            if col_idx in [2, 10, 13, 14, 15, 16]:
                cell.alignment = align_center
            else:
                cell.alignment = align_left

        print(f" ✅ 完了 ({e1})")

    col_widths = {
        2: 6, 3: 18, 4: 18, 5: 35, 6: 22, 7: 22, 8: 22, 9: 22,
        10: 10, 11: 35, 12: 35, 13: 16, 14: 16, 15: 16, 16: 14, 17: 40
    }
    for col_idx, width in col_widths.items():
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    wb_eval.save(EVAL_FILE)
    print(f"💾 「{chosen_title}」の保存が完了しました。")

print(f"\n🎉 2分野（ユーザーインタフェース・情報メディア）の厳格査読が完了しました！")