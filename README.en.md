**English** · [繁體中文](README.md)

# Image Background Remover 🪄

Remove the background from an image, **keeping only the main subject** with a fully transparent background (outputs transparent PNG).
Powered by **BiRefNet**, a top-tier background-removal model that runs locally and for free (via [rembg](https://github.com/danielgatis/rembg)) — no cloud API, no API key, no cost.

---

## Examples

| Original | Background removed (transparent PNG) |
|------|------|
| <img src="examples/before/gift-icon.png" width="180"> | <img src="examples/after/gift-icon.png" width="180"> |
| <img src="examples/before/map-icon.png" width="180"> | <img src="examples/after/map-icon.png" width="180"> |

---

## Three ways to use it

### Option 1: Drag & drop (easiest)
**Drag** an image or a whole folder **onto the "去背工具.app" icon** and release — it removes the background automatically.
Results appear in the `去背結果` folder, which opens automatically.

> ⚠️ **Drag** onto the icon — do not double-click it.

### Option 2: One-click folder mode
1. Drop the images you want processed into the **`輸入圖片`** folder
2. Double-click **`一鍵去背.command`**
3. Results appear in the **`去背結果`** folder

### Option 3: Command line (advanced / for Claude)
```bash
# One or more images
.venv/bin/python remove_bg.py image.png

# A whole folder
.venv/bin/python remove_bg.py "some-folder/"

# Common options
.venv/bin/python remove_bg.py image.png --out output --trim --matting
```

| Option | Description |
|------|------|
| `--out DIR` | Output folder (default `去背結果`) |
| `--model NAME` | Model (default `birefnet-general`; switch to `isnet-general-use` when a **light / low-contrast subject gets cut off**) |
| `--fill` | **Fill holes**: fills enclosed areas inside the subject that were misread as background (line art / solid icons, e.g. an envelope). ⚠️ It also fills intentional cut-outs (gear centers, the three dots in a speech bubble) — don't use it on those |
| `--largest` | Keep only the largest subject; remove detached fragments / floating bits |
| `--trim` | Crop away transparent margins, leaving just the subject's bounding box (good for stickers) |
| `--matting` | Enable alpha matting for finer edges |

---

## Supported formats
Input: `png / jpg / jpeg / webp / bmp / tiff` → Output: transparent `png`

## When the result isn't good — targeted fixes
- **Subject interior / lower half hollowed out or missing corners** (light-colored, too close to the background): switch to `--model isnet-general-use`.
- **Line art / hollow icon left as an outline only, middle not filled** (e.g. an envelope): add `--fill` (pair with `--largest` if needed).
- **Leftover background fragments / floating bits**: add `--largest`.
- **Rough edges**: add `--matting`.

> How it works: background removal only computes a mask of "where the subject is", then applies it back onto the **original image**; `--fill` patches enclosed holes inside the subject.
> This is *salient object* removal — by default it keeps the **single most prominent subject** in the frame; with multiple separate elements it may keep only the main one (force with `--largest`).

**Known `--fill` limitation**: it only patches enclosed holes "surrounded on all sides by the subject". If a hole touches the image edge (e.g. a cropped image), it can't be filled. Add a ring of transparent padding around the image first, then rerun.

## Environment (already set up; usually nothing to do)
- `.venv/`: Python 3.13 virtual environment with `rembg / pillow / onnxruntime / scipy / numpy` installed
- If `.venv` is broken, rebuild it:
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  ```
