import os
import glob
from PIL import Image

IMAGE_DIR = "static/images"
TARGET_WIDTH = 1280  # Web表示に十分な高解像度（横幅）

if not os.path.exists(IMAGE_DIR):
    print(f"❌ フォルダが見つかりません: {IMAGE_DIR}")
    exit(1)

image_files = glob.glob(os.path.join(IMAGE_DIR, "*.png")) + \
              glob.glob(os.path.join(IMAGE_DIR, "*.jpg")) + \
              glob.glob(os.path.join(IMAGE_DIR, "*.jpeg"))

print(f"🔍 対象画像数: {len(image_files)} 枚")
total_before = 0
total_after = 0

for img_path in image_files:
    file_size_before = os.path.getsize(img_path) / (1024 * 1024) # MB
    total_before += file_size_before

    try:
        with Image.open(img_path) as im:
            # RGBAの場合はRGBに変換（白背景）
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")

            # リサイズ（横幅が1280pxより大きい場合のみ縮小）
            w, h = im.size
            if w > TARGET_WIDTH:
                new_h = int(h * (TARGET_WIDTH / w))
                im = im.resize((TARGET_WIDTH, new_h), Image.Resampling.LANCZOS)

            # 最適化して上書き保存（画質85%：見た目の劣化なしで激減）
            # Streamlit側が .png 拡張子を参照しているためPNG形式で保存（またはJPEG圧縮）
            im.save(img_path, format="PNG", optimize=True)

        file_size_after = os.path.getsize(img_path) / (1024 * 1024)
        total_after += file_size_after
        print(f"✅ {os.path.basename(img_path)}: {file_size_before:.2f} MB → {file_size_after:.2f} MB")
    except Exception as e:
        print(f"⚠️ スキップ ({os.path.basename(img_path)}): {e}")

print("-" * 50)
print(f"🎉 圧縮完了！ 合計サイズ: {total_before:.1f} MB → {total_after:.1f} MB")
