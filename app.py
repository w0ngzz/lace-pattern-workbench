from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
PATTERN_DIR = BASE_DIR / "pattern"
TOP10_DIR = PATTERN_DIR / "top10"
MATERIAL_LIBRARY_DIR = PATTERN_DIR / "library"
MATERIAL_ORIGINAL_DIR = MATERIAL_LIBRARY_DIR / "pic" / "originals"
MATERIAL_THUMBNAIL_DIR = MATERIAL_LIBRARY_DIR / "pic" / "thumbnails"
MATERIAL_DATA_DIR = MATERIAL_LIBRARY_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
THUMBNAIL_DIR = BASE_DIR / ".cache" / "thumbnails"
WORK_ORDERS_FILE = DATA_DIR / "design_work_orders.jsonl"
MATCHER_STATE_FILE = BASE_DIR / ".runtime" / "matcher_status.json"
MATCHER_REQUEST_DIR = BASE_DIR / ".runtime" / "match_requests"
MATCHER_JOB_DIR = BASE_DIR / ".runtime" / "match_jobs"
MATCHER_RESULT_DIR = BASE_DIR / ".runtime" / "match_results"
MATCHER_STATUS_MAX_AGE_SECONDS = 12
MATCHER_RESULT_TIMEOUT_SECONDS = 120
MATCHER_ARTIFACT_RETENTION_SECONDS = 60 * 60
MATCH_FILE_URL_TTL_SECONDS = 10 * 60

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_UPLOAD_SIZE = 12 * 1024 * 1024

PATTERN_DETAILS = [
    {
        'title': '珍珠枝蔓',
        'reason': '枝叶走向清晰，精致装饰感与留白比例平衡。',
        'description': '以舒展枝蔓为主线，局部点状元素形成视觉停顿，适合强调轻盈、精致的高级感。',
        'application': '礼服局部、婚纱上身、袖片与领口装饰',
    },
    {
        'title': '密织花庭',
        'reason': '花叶层次丰富，近看细节充足，远看轮廓完整。',
        'description': '中等密度的花叶纹样保持连续节奏，在成衣大面积使用时仍具有稳定的视觉秩序。',
        'application': '连衣裙、半裙、轻礼服与面料拼接',
    },
    {
        'title': '几何花网',
        'reason': '几何骨架与自然花型结合，现代感更突出。',
        'description': '规则网格承担结构，花卉元素柔化边界，适合在经典蕾丝基础上表达年轻化方向。',
        'application': '时装上衣、套装内搭、局部透视设计',
    },
    {
        'title': '轻透散花',
        'reason': '图案分布疏朗，能够保留底层面料和肤色的呼吸感。',
        'description': '小型花簇以散点方式排列，留白充分，适合需要轻量感和层次叠穿的设计。',
        'application': '罩衫、袖片、肩部拼接与春夏裙装',
    },
    {
        'title': '浮雕团花',
        'reason': '主体花型识别度高，适合作为系列设计的视觉记忆点。',
        'description': '以饱满团花形成中心视觉，纹理密度由内向外递减，具有较强的立体浮雕感。',
        'application': '礼服重点部位、胸前装饰、裙摆定位花',
    },
    {
        'title': '对称藤蔓',
        'reason': '对称结构便于裁片定位，也更容易控制成衣视觉重心。',
        'description': '藤蔓沿轴线展开，节奏稳定而不呆板，可用于强调身体纵向线条和结构比例。',
        'application': '前中片、后背、门襟与纵向拼接',
    },
    {
        'title': '盛放大花',
        'reason': '大尺度花型具有舞台感，少量使用即可建立设计焦点。',
        'description': '放大的花瓣轮廓与细密内部纹理形成尺度反差，适合简洁廓形中的重点表达。',
        'application': '晚礼服、舞台服、裙摆和披肩',
    },
    {
        'title': '叶脉流线',
        'reason': '线性方向明确，能够自然引导裁剪和拼接走向。',
        'description': '叶片与细长茎线构成流动轨迹，视觉轻快，适合与不对称结构结合。',
        'application': '斜裁裙装、不对称上衣、袖口与侧片',
    },
    {
        'title': '留白小花',
        'reason': '小花与留白比例克制，商业应用范围较广。',
        'description': '低密度小型花卉形成安静表面，既能单独使用，也适合与其他材质叠搭。',
        'application': '日常女装、衬衫、童装与配饰',
    },
    {
        'title': '华丽满幅',
        'reason': '满幅纹理完成度高，适合快速建立系列中的高价值款。',
        'description': '连续花叶覆盖画面并保持层次变化，整体华丽但仍有可辨识的纹样节奏。',
        'application': '主推礼服、婚纱裙身、外套与陈列样衣',
    },
]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
app.config["PUBLIC_BASE_URL"] = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
app.config["MATCH_FILE_SECRET"] = os.environ.get("MATCH_FILE_SECRET", "")


def natural_sort_key(path: Path) -> tuple[int, int | str]:
    if path.stem.isdigit():
        return (0, int(path.stem))
    return (1, path.name.casefold())


def pattern_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS),
        key=natural_sort_key,
    )


def batch_updated_at(files: list[Path]) -> str:
    if not files:
        return "尚未更新"
    latest_timestamp = max(path.stat().st_mtime for path in files)
    return datetime.fromtimestamp(latest_timestamp).strftime("%Y年%m月%d日 %H:%M")


def safe_float(value: object) -> float:
    try:
        return float(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0.0


def compact_number(value: float) -> str:
    return f"{value:,.0f}"


PATTERN_TYPE_DESCRIPTIONS = {
    "巴洛克纹": "曲线饱满、装饰感强，适合礼服重点部位与强调华丽层次的设计。",
    "几何纹": "秩序清晰、节奏利落，适合现代廓形、拼接结构与年轻化系列。",
    "植物花卉纹": "取材自然、气质柔和，适合连衣裙、婚纱与轻礼服的大面积应用。",
    "民族风纹": "纹样辨识度高、文化气息浓郁，适合主题系列与局部视觉焦点。",
    "纯色": "表面克制、搭配弹性高，适合作为基础面料或与复杂材质叠搭。",
    "蕾丝镂空": "通透层次鲜明，可用于袖片、领口、罩层与需要轻盈感的区域。",
}


def material_library_source() -> Path | None:
    if not MATERIAL_DATA_DIR.exists():
        return None
    csv_files = [path for path in MATERIAL_DATA_DIR.glob("*.csv") if path.is_file()]
    return max(csv_files, key=lambda path: path.stat().st_size, default=None)


def material_lifecycle(rows: list[dict[str, str]]) -> str:
    sales_rows = [row for row in rows if safe_float(row.get("销量(米)")) > 0]
    if not sales_rows:
        return "筹备中"
    if len(sales_rows) <= 2:
        return "新品期"

    latest_growth = safe_float(sales_rows[-1].get("环比增长"))
    if latest_growth < -0.08:
        return "衰退期"
    if latest_growth > 0.12:
        return "成长期"
    return "成熟期"


def material_image_urls(style_id: int) -> tuple[str | None, str | None]:
    thumbnail = MATERIAL_THUMBNAIL_DIR / f"{style_id}_thumb.jpg"
    original = next(
        (
            MATERIAL_ORIGINAL_DIR / f"{style_id}{extension}"
            for extension in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
            if (MATERIAL_ORIGINAL_DIR / f"{style_id}{extension}").is_file()
        ),
        None,
    )
    thumbnail_url = (
        url_for("library_thumbnail", filename=thumbnail.name) if thumbnail.is_file() else None
    )
    original_url = url_for("library_image", filename=original.name) if original else None
    return thumbnail_url or original_url, original_url or thumbnail_url


def load_material_styles() -> tuple[list[dict], Path | None]:
    source = material_library_source()
    grouped_rows: dict[int, list[dict[str, str]]] = {}

    if source:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    style_id = int(float(row.get("编号ID", "")))
                except (TypeError, ValueError):
                    continue
                grouped_rows.setdefault(style_id, []).append(row)

    for path in pattern_files(MATERIAL_ORIGINAL_DIR):
        if path.stem.isdigit():
            grouped_rows.setdefault(int(path.stem), [])

    styles = []
    for style_id, rows in sorted(grouped_rows.items()):
        rows.sort(key=lambda row: row.get("季度", ""))
        latest = rows[-1] if rows else {}
        total_sales = sum(safe_float(row.get("销量(米)")) for row in rows)
        total_revenue = sum(safe_float(row.get("销售额(元)")) for row in rows)
        total_orders = sum(safe_float(row.get("订单数")) for row in rows)
        price = total_revenue / total_sales if total_sales else 0
        pattern_type = latest.get("花纹类型") or latest.get("分类") or "未分类"
        lifecycle = material_lifecycle(rows)
        image_url, original_url = material_image_urls(style_id)
        growth = safe_float(latest.get("环比增长"))

        styles.append(
            {
                "id": style_id,
                "code": latest.get("款式名称") or f"LACE-{style_id:03d}",
                "category": pattern_type,
                "pattern_type": pattern_type,
                "width": latest.get("宽度") or latest.get("幅宽") or "未标注",
                "material": latest.get("材质") or latest.get("成分") or "未标注",
                "usage": latest.get("用途") or latest.get("推荐用途") or "未标注",
                "color": latest.get("颜色") or "未标注",
                "lifecycle": lifecycle,
                "listing_status": latest.get("上市状态") or "资料待完善",
                "latest_quarter": latest.get("季度") or "暂无季度数据",
                "total_sales": total_sales,
                "total_sales_label": compact_number(total_sales),
                "total_revenue": total_revenue,
                "total_revenue_label": compact_number(total_revenue),
                "price": price,
                "price_label": f"{price:,.1f}" if price else "--",
                "orders_label": compact_number(total_orders),
                "stock_label": compact_number(safe_float(latest.get("期末库存(米)"))),
                "growth_label": f"{growth:+.1%}" if rows else "--",
                "image_url": image_url,
                "original_url": original_url,
                "description": latest.get("描述")
                or PATTERN_TYPE_DESCRIPTIONS.get(
                    pattern_type,
                    "款式资料已纳入本店素材库，可结合客户用途、面料手感与成衣部位进一步评估。",
                ),
            }
        )
    return styles, source


def thumbnail_path(source: Path) -> Path:
    source_stamp = source.stat().st_mtime_ns
    return THUMBNAIL_DIR / f"{source.parent.name}-{source.stem}-{source_stamp}.webp"


@app.get("/")
def index():
    all_files = pattern_files(TOP10_DIR)
    files = all_files[:10]
    patterns = [
        {
            "rank": rank,
            "name": path.name,
            "image_url": url_for("pattern_image", filename=path.name),
            **PATTERN_DETAILS[rank - 1],
        }
        for rank, path in enumerate(files, start=1)
    ]
    return render_template(
        "index.html",
        patterns=patterns,
        updated_at=batch_updated_at(all_files),
        month_label=datetime.now().strftime("%b · %Y").upper(),
    )


@app.get("/library")
def library_page():
    styles, source = load_material_styles()
    asset_files = pattern_files(MATERIAL_ORIGINAL_DIR) + pattern_files(MATERIAL_THUMBNAIL_DIR)
    update_sources = asset_files + ([source] if source else [])
    category_counts = {}
    for style in styles:
        category_counts[style["category"]] = category_counts.get(style["category"], 0) + 1
    hot_categories = sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))[:6]

    def filter_values(field: str) -> list[str]:
        return sorted({style[field] for style in styles if style[field] != "未标注"})

    return render_template(
        "library.html",
        styles=styles,
        categories=filter_values("category"),
        widths=filter_values("width"),
        materials=filter_values("material"),
        usages=filter_values("usage"),
        colors=filter_values("color"),
        hot_categories=hot_categories,
        style_count=len(styles),
        total_sales_label=compact_number(sum(style["total_sales"] for style in styles)),
        total_revenue_label=compact_number(sum(style["total_revenue"] for style in styles)),
        updated_at=batch_updated_at(update_sources),
    )


def current_matcher_status() -> dict:
    status = {"online": False, "workerId": None, "message": "图案匹配服务离线"}
    try:
        state = json.loads(MATCHER_STATE_FILE.read_text(encoding="utf-8"))
        heartbeat_age = time.time() - float(state.get("updatedAt", 0))
        online = bool(state.get("online")) and heartbeat_age <= MATCHER_STATUS_MAX_AGE_SECONDS
        status = {
            "online": online,
            "workerId": state.get("workerId") if online else None,
            "message": "图案匹配服务在线" if online else "图案匹配服务离线",
        }
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        pass

    return status


@app.get("/api/matcher-status")
def matcher_status():
    status = current_matcher_status()

    response = jsonify(status)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/pattern-images/<path:filename>")
def pattern_image(filename: str):
    return send_pattern_thumbnail(TOP10_DIR, filename)


@app.get("/library-images/<path:filename>")
def library_image(filename: str):
    return send_pattern_thumbnail(MATERIAL_ORIGINAL_DIR, filename)


@app.get("/library-thumbnails/<path:filename>")
def library_thumbnail(filename: str):
    safe_name = Path(filename).name
    source = MATERIAL_THUMBNAIL_DIR / safe_name
    if safe_name != filename or not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        abort(404)
    return send_file(source, conditional=True, max_age=3600)


def send_pattern_thumbnail(directory: Path, filename: str):
    safe_name = Path(filename).name
    source = directory / safe_name
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


def match_file_signature(filename: str, expires: int) -> str:
    secret = str(app.config.get("MATCH_FILE_SECRET") or "").encode("utf-8")
    message = f"{filename}\n{expires}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def match_file_download_url(filename: str) -> str:
    expires = int(time.time()) + MATCH_FILE_URL_TTL_SECONDS
    signature = match_file_signature(filename, expires)
    base_url = str(app.config.get("PUBLIC_BASE_URL") or request.url_root).rstrip("/")
    query = urlencode({"expires": expires, "signature": signature})
    return f"{base_url}/api/match-files/{filename}?{query}"


@app.get("/api/match-files/<path:filename>")
def download_match_file(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename or not app.config.get("MATCH_FILE_SECRET"):
        abort(404)

    try:
        expires = int(request.args.get("expires", ""))
    except ValueError:
        abort(403)

    supplied_signature = request.args.get("signature", "")
    expected_signature = match_file_signature(safe_name, expires)
    if expires < int(time.time()) or not hmac.compare_digest(
        supplied_signature,
        expected_signature,
    ):
        abort(403)

    source = UPLOAD_DIR / safe_name
    if not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        abort(404)

    response = send_file(
        source,
        conditional=True,
        as_attachment=True,
        download_name=safe_name,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = path.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_file.replace(path)


def cleanup_expired_match_artifacts() -> None:
    if not MATCHER_JOB_DIR.exists():
        return

    cutoff = time.time() - MATCHER_ARTIFACT_RETENTION_SECONDS
    for job_file in MATCHER_JOB_DIR.glob("*.json"):
        try:
            if job_file.stat().st_mtime >= cutoff:
                continue
            job = json.loads(job_file.read_text(encoding="utf-8"))
            stored_name = Path(str(job.get("storedName", ""))).name
            if stored_name:
                (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
            (MATCHER_RESULT_DIR / job_file.name).unlink(missing_ok=True)
            job_file.unlink(missing_ok=True)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue


def material_file_for_index(image_index: int) -> Path | None:
    return next(
        (
            path
            for path in pattern_files(MATERIAL_ORIGINAL_DIR)
            if path.stem.isdigit() and int(path.stem) == image_index
        ),
        None,
    )


def normalized_worker_matches(payload: dict) -> list[dict]:
    matches = []
    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        return matches

    for raw_match in raw_matches[:20]:
        if not isinstance(raw_match, dict):
            continue
        try:
            image_index = int(raw_match.get("imageIndex", raw_match.get("materialId")))
            similarity = float(raw_match.get("similarity", raw_match.get("score")))
        except (TypeError, ValueError):
            continue
        if image_index < 1 or not 0 <= similarity <= 1:
            continue

        material_file = material_file_for_index(image_index)
        if material_file is None:
            continue
        matches.append(
            {
                "imageIndex": image_index,
                "similarity": round(similarity, 4),
                "fileName": material_file.name,
                "matchedImage": url_for("library_image", filename=material_file.name),
                "previewUrl": url_for("preview", pattern=material_file.name),
            }
        )

    matches.sort(key=lambda item: item["similarity"], reverse=True)
    return matches[:5]


@app.get("/api/match-results/<request_id>")
def match_result(request_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        abort(404)

    job_file = MATCHER_JOB_DIR / f"{request_id}.json"
    if not job_file.is_file():
        abort(404)
    try:
        job = json.loads(job_file.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return jsonify({"ok": False, "status": "failed", "message": "匹配任务状态读取失败。"}), 500

    result_file = MATCHER_RESULT_DIR / f"{request_id}.json"
    if not result_file.is_file():
        elapsed = time.time() - float(job.get("createdAtEpoch", 0))
        if elapsed >= MATCHER_RESULT_TIMEOUT_SECONDS:
            return jsonify(
                {
                    "ok": False,
                    "status": "timeout",
                    "requestId": request_id,
                    "message": "图案识别服务响应超时，请重新上传或创建设计工单。",
                }
            ), 504
        return jsonify(
            {
                "ok": True,
                "status": "processing",
                "requestId": request_id,
                "elapsedSeconds": round(max(0, elapsed), 1),
            }
        ), 202

    try:
        worker_result = json.loads(result_file.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return jsonify({"ok": False, "status": "failed", "message": "Worker 匹配结果读取失败。"}), 500

    if not worker_result.get("ok"):
        error = worker_result.get("error")
        error_message = error.get("message") if isinstance(error, dict) else None
        return jsonify(
            {
                "ok": False,
                "status": "failed",
                "requestId": request_id,
                "message": error_message or "图案识别服务处理失败，请稍后重试。",
                "error": error if isinstance(error, dict) else None,
            }
        ), 502

    matches = normalized_worker_matches(worker_result)
    matched = bool(worker_result.get("matched", bool(matches))) and bool(matches)
    response = {
        "ok": True,
        "status": "completed",
        "requestId": request_id,
        "uploadFileName": job.get("fileName"),
        "matched": matched,
        "message": "匹配成功" if matched else "暂未找到您想要的款式",
        "matches": matches,
        "elapsedMs": worker_result.get("elapsedMs"),
        "modelVersion": worker_result.get("modelVersion"),
    }
    if matched:
        best_match = matches[0]
        response.update(
            {
                "imageIndex": best_match["imageIndex"],
                "similarity": best_match["similarity"],
                "matchedFileName": best_match["fileName"],
                "matchedImage": best_match["matchedImage"],
                "previewUrl": best_match["previewUrl"],
            }
        )
    return jsonify(response)


@app.post("/api/match")
def match_pattern():
    if not current_matcher_status()["online"]:
        return jsonify({"ok": False, "message": "图案识别服务当前不在线，暂时无法匹配。"}), 503

    uploaded = request.files.get("pattern")
    if uploaded is None or not uploaded.filename:
        return jsonify({"ok": False, "message": "请选择需要识别的图案文件。"}), 400

    original_name = Path(uploaded.filename).name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({"ok": False, "message": "仅支持 PNG、JPG、WEBP 或 BMP 图片。"}), 400
    if not app.config.get("MATCH_FILE_SECRET"):
        return jsonify({"ok": False, "message": "图案下载服务尚未配置，暂时无法匹配。"}), 503

    cleanup_expired_match_artifacts()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    uploaded.save(UPLOAD_DIR / secure_filename(stored_name))

    request_id = uuid.uuid4().hex
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    match_request = {
        "type": "match_request",
        "requestId": request_id,
        "fileName": original_name,
        "storedName": stored_name,
        "downloadUrl": match_file_download_url(stored_name),
        "createdAt": created_at,
    }
    write_json_atomic(
        MATCHER_JOB_DIR / f"{request_id}.json",
        {
            "requestId": request_id,
            "fileName": original_name,
            "storedName": stored_name,
            "createdAt": created_at,
            "createdAtEpoch": time.time(),
        },
    )
    request_file = MATCHER_REQUEST_DIR / f"{request_id}.json"
    write_json_atomic(request_file, match_request)

    return jsonify(
        {
            "ok": True,
            "status": "processing",
            "requestId": request_id,
            "message": "图案匹配任务已提交。",
            "fileName": original_name,
        }
    ), 202


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


def start_local_match_gateway() -> subprocess.Popen | None:
    gateway_script = BASE_DIR / 'dev_match_gateway.py'
    if not gateway_script.exists():
        print('[dev] dev_match_gateway.py not found; matcher gateway was not started.', flush=True)
        return None

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        if connection.connect_ex(('127.0.0.1', 8765)) == 0:
            print('[dev] matcher gateway already running on ws://127.0.0.1:8765', flush=True)
            return None

    process = subprocess.Popen([sys.executable, str(gateway_script)], cwd=BASE_DIR)
    print(f'[dev] matcher gateway started automatically (pid={process.pid})', flush=True)
    return process


def stop_local_match_gateway(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    print('[dev] matcher gateway stopped.', flush=True)


if __name__ == "__main__":
    local_gateway_process = start_local_match_gateway()
    try:
        app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
    finally:
        stop_local_match_gateway(local_gateway_process)
