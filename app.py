from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
PATTERN_DIR = BASE_DIR / "pattern"
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
THUMBNAIL_DIR = BASE_DIR / ".cache" / "thumbnails"
WORK_ORDERS_FILE = DATA_DIR / "design_work_orders.jsonl"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_UPLOAD_SIZE = 12 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


def natural_sort_key(path: Path) -> tuple[int, int | str]:
    if path.stem.isdigit():
        return (0, int(path.stem))
    return (1, path.name.casefold())


def pattern_files() -> list[Path]:
    if not PATTERN_DIR.exists():
        return []
    return sorted(
        (path for path in PATTERN_DIR.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS),
        key=natural_sort_key,
    )


def batch_updated_at(files: list[Path]) -> str:
    if not files:
        return "尚未更新"
    latest_timestamp = max(path.stat().st_mtime for path in files)
    return datetime.fromtimestamp(latest_timestamp).strftime("%Y年%m月%d日 %H:%M")


def thumbnail_path(source: Path) -> Path:
    source_stamp = source.stat().st_mtime_ns
    return THUMBNAIL_DIR / f"{source.stem}-{source_stamp}.webp"


@app.get("/")
def index():
    all_files = pattern_files()
    files = all_files[:10]
    patterns = [
        {
            "rank": rank,
            "name": path.name,
            "image_url": url_for("pattern_image", filename=path.name),
        }
        for rank, path in enumerate(files, start=1)
    ]
    return render_template(
        "index.html",
        patterns=patterns,
        updated_at=batch_updated_at(all_files),
        month_label=datetime.now().strftime("%b · %Y").upper(),
    )


@app.get("/pattern-images/<path:filename>")
def pattern_image(filename: str):
    safe_name = Path(filename).name
    source = PATTERN_DIR / safe_name
    if safe_name != filename or not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        abort(404)

    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    cached = thumbnail_path(source)
    if not cached.exists():
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(cached, "WEBP", quality=84, method=6)
    return send_file(cached, mimetype="image/webp", conditional=True, max_age=3600)


@app.post("/api/match")
def match_pattern():
    uploaded = request.files.get("pattern")
    if uploaded is None or not uploaded.filename:
        return jsonify({"ok": False, "message": "请选择需要识别的图案文件。"}), 400

    original_name = Path(uploaded.filename).name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({"ok": False, "message": "仅支持 PNG、JPG、WEBP 或 BMP 图片。"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    uploaded.save(UPLOAD_DIR / secure_filename(stored_name))

    library_files = pattern_files()
    library_by_name = {path.name.casefold(): path for path in library_files}

    # 临时匹配规则：只比较上传文件名与 pattern 素材库文件名，后续替换为图像相似度算法。
    matched = library_by_name.get(original_name.casefold())
    if matched:
        return jsonify(
            {
                "ok": True,
                "matched": True,
                "message": "匹配成功",
                "fileName": original_name,
                "matchedImage": url_for("pattern_image", filename=matched.name),
                "previewUrl": url_for("preview", pattern=matched.name),
            }
        )

    return jsonify(
        {
            "ok": True,
            "matched": False,
            "message": "暂未找到您想要的款式",
            "fileName": original_name,
        }
    )


@app.get("/preview")
def preview():
    pattern_name = Path(request.args.get("pattern", "")).name
    return render_template("preview.html", pattern_name=pattern_name)


@app.post("/api/work-orders")
def create_design_work_order():
    payload = request.get_json(silent=True) or {}
    customer_name = str(payload.get("customerName", "")).strip()
    customer_contact = str(payload.get("customerContact", "")).strip()
    upload_file_name = Path(str(payload.get("uploadFileName", ""))).name
    match_status = str(payload.get("matchStatus", "unknown"))

    if not customer_name or len(customer_name) > 50:
        return jsonify({"ok": False, "message": "请填写有效的客户姓名（不超过 50 个字符）。"}), 400
    if not customer_contact or len(customer_contact) > 100:
        return jsonify({"ok": False, "message": "请填写有效的客户联系方式（不超过 100 个字符）。"}), 400
    if not re.search(r"[0-9A-Za-z@]", customer_contact):
        return jsonify({"ok": False, "message": "客户联系方式似乎不完整，请检查后重试。"}), 400
    if match_status not in {"not_matched", "rejected"}:
        return jsonify({"ok": False, "message": "仅未匹配或已否认的款式可以创建设计工单。"}), 400

    work_order_no = f"LS-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "id": uuid.uuid4().hex,
        "workOrderNo": work_order_no,
        "customerName": customer_name,
        "customerContact": customer_contact,
        "uploadFileName": upload_file_name,
        "matchStatus": match_status,
        "status": "pending",
        "createdByRole": "designer",
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with WORK_ORDERS_FILE.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")

    return jsonify(
        {
            "ok": True,
            "workOrderNo": work_order_no,
            "message": f"设计工单 {work_order_no} 已创建，客户信息已登记。",
        }
    )


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"ok": False, "message": "图片不能超过 12 MB。"}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
