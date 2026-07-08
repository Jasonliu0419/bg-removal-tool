#!/bin/bash
# 一鍵去背(資料夾模式)
# 用法:把要去背的圖片放進「輸入圖片」資料夾,然後 double-click 這個檔案。
# 結果會輸出到「去背結果」資料夾並自動打開。

set -euo pipefail

# 切到這個腳本所在的資料夾(不管從哪裡點都正確)
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

VENV_PY="$DIR/.venv/bin/python"
INPUT_DIR="$DIR/輸入圖片"
OUTPUT_DIR="$DIR/去背結果"

echo "========================================"
echo "   🪄  圖片去背小工具(一鍵模式)"
echo "========================================"

if [ ! -x "$VENV_PY" ]; then
  echo "❌ 找不到虛擬環境:$VENV_PY"
  echo "   請先在此資料夾建立 .venv 並安裝 rembg。"
  read -r -p "按 Enter 關閉..." _
  exit 1
fi

mkdir -p "$INPUT_DIR"

# 檢查輸入夾有沒有圖
shopt -s nullglob nocaseglob
imgs=("$INPUT_DIR"/*.png "$INPUT_DIR"/*.jpg "$INPUT_DIR"/*.jpeg "$INPUT_DIR"/*.webp "$INPUT_DIR"/*.bmp "$INPUT_DIR"/*.tiff)
shopt -u nullglob nocaseglob

if [ ${#imgs[@]} -eq 0 ]; then
  echo "📂 「輸入圖片」資料夾是空的。"
  echo "   請把要去背的圖片放進去,再點一次我。"
  open "$INPUT_DIR"
  read -r -p "按 Enter 關閉..." _
  exit 0
fi

echo "找到 ${#imgs[@]} 張圖,開始去背(第一次可能較久)..."
echo ""

# 關掉 -e,自己判斷結束碼:0=全部成功 1=全部失敗 2=部分失敗
set +e
"$VENV_PY" "$DIR/remove_bg.py" "$INPUT_DIR" --out "$OUTPUT_DIR"
rc=$?
set -e

echo ""
case "$rc" in
  0) echo "✅ 全部完成!正在打開結果資料夾..." ; open "$OUTPUT_DIR" ;;
  2) echo "⚠️  部分圖片去背失敗(請看上方 ❌ 行),成功的已輸出。" ; open "$OUTPUT_DIR" ;;
  *) echo "❌ 去背失敗,請看上方錯誤訊息。" ;;
esac
read -r -p "按 Enter 關閉這個視窗..." _
