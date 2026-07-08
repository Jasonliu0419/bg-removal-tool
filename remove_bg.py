#!/usr/bin/env python3
"""圖片去背小工具 — 用 rembg (BiRefNet) 把圖片去背,只留中央主體。

用法:
    python remove_bg.py <檔案或資料夾...> [選項]

範例:
    python remove_bg.py "pupu app 新圖示/"
    python remove_bg.py a.png b.jpg --out 去背結果 --trim
    python remove_bg.py 信封.png --fill                    # 線稿/實心圖示補洞
    python remove_bg.py 便便.png --model isnet-general-use  # 低對比主體

選項:
    --out DIR       輸出資料夾(預設: 去背結果)
    --model NAME    去背模型(預設: birefnet-general)
                    低對比、淡色主體被切掉時可改用 isnet-general-use
    --fill          補洞:把主體內部被誤判為背景的「封閉區域」填實,
                    適合線稿/實心圖示(例如信封輪廓)。
                    注意:會一併填掉「刻意鏤空」的孔(齒輪中心、對話框三點),
                    那類圖示請勿加此選項。
    --largest       只保留最大的主體,清掉分離的碎塊/浮動小裝飾。
    --trim          裁掉四周透明邊,只留主體外接框
    --matting       開啟 alpha matting 讓邊緣更乾淨(難分離的圖用)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np
    from PIL.Image import Image as ImageType

# 支援的輸入副檔名(小寫)
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
DEFAULT_OUTPUT_DIR = "去背結果"
DEFAULT_MODEL = "birefnet-general"
ALPHA_THRESHOLD = 8   # 判定「前景」的 alpha 門檻(0-255),取低值以保留細線
FILL_RADIUS = 2       # 補洞前的膨脹半徑,用來橋接細線的像素級斷點
FEATHER_SIGMA = 0.6   # 精修後對邊緣做的輕微羽化,抗鋸齒


def collect_images(inputs: list[str]) -> list[Path]:
    """把使用者給的檔案/資料夾展開成一份去重、排序後的圖片清單。"""
    images: list[Path] = []
    seen: set[Path] = set()

    for raw in inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"⚠️  找不到,略過: {raw}", file=sys.stderr)
            continue

        candidates: list[Path]
        if path.is_dir():
            candidates = sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            )
            if not candidates:
                print(f"⚠️  資料夾內沒有支援的圖片: {path}", file=sys.stderr)
        elif path.suffix.lower() in SUPPORTED_SUFFIXES:
            candidates = [path]
        else:
            print(f"⚠️  不支援的格式,略過: {path}", file=sys.stderr)
            candidates = []

        for c in candidates:
            resolved = c.resolve()
            if resolved not in seen:
                seen.add(resolved)
                images.append(c)

    return images


def _disk(radius: int) -> "_np.ndarray":
    """回傳半徑 radius 的圓形結構元素(供形態學運算用)。"""
    import numpy as np

    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    return (x * x + y * y) <= radius * radius


def _largest_component(mask: "_np.ndarray") -> "_np.ndarray":
    """只保留 mask 中面積最大的連通區。"""
    from scipy import ndimage

    labels, n = ndimage.label(mask)
    if n <= 1:
        return mask
    sizes = ndimage.sum(mask, labels, index=range(1, n + 1))
    return labels == (1 + int(sizes.argmax()))


def refine_alpha(alpha: "_np.ndarray", *, fill: bool, largest: bool) -> "_np.ndarray":
    """依選項精修 alpha 遮罩:補洞、只留最大連通區、輕微羽化。"""
    import numpy as np
    from scipy import ndimage

    a = alpha
    changed = False

    if fill:
        # 膨脹→補洞→侵蝕:填實封閉區域,同時橋接細線的像素級斷點,再縮回原尺寸
        st = _disk(FILL_RADIUS)
        core = alpha > ALPHA_THRESHOLD
        core = ndimage.binary_dilation(core, st)
        core = ndimage.binary_fill_holes(core)
        core = ndimage.binary_erosion(core, st)
        a = np.maximum(a, core.astype(np.uint8) * 255)
        changed = True

    if largest:
        core = _largest_component(a > ALPHA_THRESHOLD)
        a = np.where(core, a, np.uint8(0))
        changed = True

    if changed:
        a = ndimage.gaussian_filter(a.astype(np.float32), sigma=FEATHER_SIGMA)
        a = np.clip(a, 0, 255).astype(np.uint8)
    return a


def trim_transparent(image: "ImageType") -> "ImageType":
    """裁掉四周全透明的邊,只留主體外接框。若整張全透明則原樣回傳。

    明確傳 alpha_only=True 只依 alpha 判邊界:因為本工具的透明區仍保留原圖 RGB,
    若看 RGB 會誤判整張非空而裁不掉透明邊(需 Pillow>=9.2)。
    """
    bbox = image.getbbox(alpha_only=True)
    return image.crop(bbox) if bbox else image


def unique_output_path(out_dir: Path, stem: str, used: set[Path]) -> Path:
    """回傳本批次尚未用過的輸出路徑;同名(不同來源)時自動加 _2/_3 後綴,避免無聲覆蓋。"""
    candidate = out_dir / f"{stem}.png"
    n = 2
    while candidate in used:
        candidate = out_dir / f"{stem}_{n}.png"
        n += 1
    used.add(candidate)
    return candidate


def build_session(model_name: str):
    """建立 rembg session;模型名稱錯誤時給清楚的訊息。"""
    from rembg import new_session

    try:
        return new_session(model_name)
    except Exception as exc:  # 模型下載失敗 / 名稱錯誤
        raise SystemExit(
            f"❌ 無法載入模型 '{model_name}': {exc}\n"
            f"   請確認名稱正確,或改用 --model isnet-general-use"
        )


def remove_one(
    src: Path, out_path: Path, session, *,
    trim: bool, matting: bool, fill: bool, largest: bool,
) -> None:
    """對單張圖去背並輸出透明 PNG 到指定路徑。

    關鍵:去背只算出 alpha 遮罩,再把它套回「原圖 RGB」——
    因為 rembg 會把背景區的 RGB 歸零(變黑),若補洞後沿用它的 RGB,
    被救回的區域會變成黑色。用原圖 RGB 才能保留主體真實顏色。
    """
    import numpy as np
    from PIL import Image
    from rembg import remove

    with Image.open(src) as im:
        original = im.convert("RGBA")
        rgb = np.array(original)[:, :, :3]

    # post_process_mask=True:清掉零星雜點、讓遮罩更乾淨(複雜場景殘影較少)
    cut = remove(original, session=session, alpha_matting=matting, post_process_mask=True)
    alpha = np.array(cut)[:, :, 3]

    alpha = refine_alpha(alpha, fill=fill, largest=largest)

    result = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    if trim:
        result = trim_transparent(result)
    result.save(out_path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="圖片去背小工具 (rembg / BiRefNet)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("inputs", nargs="+", help="圖片檔或資料夾(可多個)")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_DIR, help="輸出資料夾")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="去背模型名稱")
    parser.add_argument("--fill", action="store_true", help="補洞:填實主體內部封閉區域(線稿/實心圖示用)")
    parser.add_argument("--largest", action="store_true", help="只留最大主體,清掉碎塊/浮動裝飾")
    parser.add_argument("--trim", action="store_true", help="裁掉四周透明邊")
    parser.add_argument("--matting", action="store_true", help="開啟 alpha matting")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    images = collect_images(args.inputs)
    if not images:
        print("❌ 沒有可處理的圖片。", file=sys.stderr)
        return 1

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    flags = []
    if args.fill:
        flags.append("補洞")
    if args.largest:
        flags.append("只留最大主體")
    tag = ("," + "+".join(flags)) if flags else ""
    print(f"🖼️  共 {len(images)} 張,模型={args.model}{tag},輸出→ {out_dir}/")
    session = build_session(args.model)

    ok = 0
    used: set[Path] = set()
    total = len(images)
    for idx, src in enumerate(images, 1):
        out_path = unique_output_path(out_dir, src.stem, used)
        try:
            remove_one(
                src, out_path, session,
                trim=args.trim, matting=args.matting,
                fill=args.fill, largest=args.largest,
            )
            ok += 1
            print(f"  [{idx}/{total}] ✅ {src.name} → {out_path.name}")
        except Exception as exc:  # 單張失敗不中斷整批
            used.discard(out_path)  # 失敗就釋放這個檔名,不佔用
            print(f"  [{idx}/{total}] ❌ {src.name}: {exc}", file=sys.stderr)

    print(f"\n完成: {ok}/{total} 張成功。結果在 {out_dir}/")
    if ok == 0:
        return 1        # 全部失敗
    if ok < total:
        return 2        # 部分失敗
    return 0            # 全部成功


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
