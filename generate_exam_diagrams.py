import os
import sqlite3
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai

# 日本語フォント設定（Mac標準）
plt.rcParams['font.family'] = 'Hiragino Sans'

# Gemini API の設定（環境変数 GEMINI_API_KEY を参照）
API_KEY = os.environ.get("GEMINI_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

TARGET_SUBCATEGORIES = [
    "3. コンピュータ構成要素",
    "5. ソフトウェア",
    "9. データベース",
    "10. ネットワーク",
    "11. セキュリティ",
    "12. システム開発技術",
    "22. 企業活動"
]

DB_FILE = "fe_study.db"
IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)


def generate_exam_oriented_content(term_name, sub_category, official_def):
    """
    Gemini API を使って試験直結テキストと横長図解用の要素データを生成する
    """
    if not model:
        # APIキーがない場合のフォールバック（動作テスト用）
        return {
            "exam_point": f"{term_name}に関する過去問では、前提条件と処理結果の組み合わせが頻出します。",
            "intuitive_guide": f"試験問題では、どのような状態からどのような結果へ変化するのかというロジックが問われます。",
            "diagram_data": {
                "left_box": f"入力・前提状態\n({term_name})",
                "right_box": "出力・試験正解肢\n(判定結果)",
                "arrow_label": "処理・判定条件",
                "key_takeaway": "選択肢では矢印の移行条件が正誤の決め手"
            }
        }

    prompt = f"""
あなたは基本情報技術者試験（科目A）の指導のプロです。
以下の用語について、初学者が過去問の正解肢・誤答肢を見抜けるようになるための「試験直結解説」と「概念図解の構成データ」をJSON形式で出力してください。

【対象用語】: {term_name}
【分類】: {sub_category}
【公式定義】: {official_def}

---
■ 注意事項
・画像生成（図解描画）用のデータには、用語のタイトルや大見出しを含めないでください（図の中には純粋な概念・状態・処理のみを記載させるため）。
・図解要素は簡潔にし、文字あふれを防ぐこと。

■ 出力要件（厳密なJSON形式のみを出力すること。Markdownのコードブロック構文 ```json は含めないか、パース可能な形式にすること）
{{
  "exam_point": "過去問の選択肢で頻出する言い換えパターンや正解の決め手となるキーワード（1〜2文）",
  "intuitive_guide": "なぜその仕組みが必要なのか、動作ロジックを初学者向けに解説（3〜4行）",
  "diagram_data": {{
    "left_box": "入力・前提条件・状態A（タイトルは含めず、概念のみ。全角15文字以内）",
    "right_box": "出力・結果・状態B（タイトルは含めず、概念のみ。全角15文字以内）",
    "arrow_label": "変化のトリガーやアルゴリズム（全角12文字以内）",
    "key_takeaway": "図の下部に添える試験攻略の着眼点メモ（全角25文字以内）"
  }}
}}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # ```json などのマークダウンタグを除去
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())
    except Exception as e:
        print(f"⚠️ API生成エラー ({term_name}): {e}")
        return None


def draw_concept_diagram(diagram_data, save_path):
    """
    タイトルを省き、純粋な左右の対比・遷移と攻略メモに絞った16:9横長図を描画する
    """
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150) # 16:9 比率
    ax.set_facecolor('#F8FAFC')
    fig.patch.set_facecolor('#F8FAFC')

    left_text = diagram_data.get("left_box", "前提・状態A")
    right_text = diagram_data.get("right_box", "結果・状態B")
    arrow_text = diagram_data.get("arrow_label", "処理・アルゴリズム")
    takeaway = diagram_data.get("key_takeaway", "選択肢の移行条件に注目")

    # 左ボックス（前提・状態A）
    box_left = patches.FancyBboxPatch((0.08, 0.32), 0.34, 0.44,
                                      boxstyle="round,pad=0.03,rounding_size=0.05",
                                      fc="#EFF6FF", ec="#3B82F6", lw=2.5)
    ax.add_patch(box_left)
    ax.text(0.25, 0.54, left_text, ha='center', va='center', fontsize=16, 
            color='#1E3A8A', multialignment='center', weight='bold')

    # 中央の矢印と処理条件
    ax.annotate('', xy=(0.58, 0.54), xytext=(0.42, 0.54),
                arrowprops=dict(facecolor='#0284C7', edgecolor='#0284C7', width=6, headwidth=16))
    ax.text(0.50, 0.65, arrow_text, ha='center', va='center', fontsize=14, weight='bold', color='#0369A1',
            bbox=dict(boxstyle="round,pad=0.4", fc="#E0F2FE", ec="#38BDF8", lw=1.5))

    # 右ボックス（結果・状態B）
    box_right = patches.FancyBboxPatch((0.58, 0.32), 0.34, 0.44,
                                       boxstyle="round,pad=0.03,rounding_size=0.05",
                                       fc="#FEF2F2", ec="#EF4444", lw=2.5)
    ax.add_patch(box_right)
    ax.text(0.75, 0.54, right_text, ha='center', va='center', fontsize=16, 
            color='#7F1D1D', multialignment='center', weight='bold')

    # 下部の試験攻略メモバー（横長バナーの下部に配置）
    ax.text(0.5, 0.12, f"★ 試験攻略の着眼点：{takeaway}",
            ha='center', va='center', fontsize=13, weight='bold', color='#1E293B',
            bbox=dict(boxstyle="square,pad=0.6", fc="#FFFFFF", ec="#94A3B8", lw=1.5))

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches='tight')
    plt.close()


def run_pipeline(limit=5):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    query = """
        SELECT id, term_name, sub_category, official_def 
        FROM terms 
        WHERE sub_category IN ({}) 
        AND (image_path IS NULL OR trim(image_path) = '' OR image_path = 'None')
        LIMIT ?;
    """.format(','.join(['?'] * len(TARGET_SUBCATEGORIES)))

    params = TARGET_SUBCATEGORIES + [limit]
    cur.execute(query, params)
    targets = cur.fetchall()

    if not targets:
        print("💡 対象7分野に未処理の用語はありません。")
        conn.close()
        return

    print(f"🚀 {len(targets)} 件の用語を処理します（タイトルを省いた横長図解と試験直結解説を生成）...")

    for row in targets:
        term_id, term_name, sub_cat, off_def = row
        print(f"▶ 処理中: [{sub_cat}] {term_name}")

        result = generate_exam_oriented_content(term_name, sub_cat, off_def)
        if not result:
            continue

        # 1. 図解の描画と保存（タイトルなし・16:9）
        img_filename = f"{IMAGE_DIR}/{term_name}.png"
        draw_concept_diagram(result["diagram_data"], img_filename)

        # 2. テキストの統合（試験の決め手 ＋ ロジック解説）
        combined_intuitive = f"【試験の決め手】\n{result['exam_point']}\n\n【概念解説】\n{result['intuitive_guide']}"

        # 3. DBの更新（解説文と画像パス）
        cur.execute("""
            UPDATE terms 
            SET intuitive_def = ?, image_path = ? 
            WHERE id = ?;
        """, (combined_intuitive, img_filename, term_id))

    conn.commit()
    conn.close()
    print("✅ 処理が完了し、DBと画像フォルダに反映されました！")


if __name__ == "__main__":
    run_pipeline(limit=5)
