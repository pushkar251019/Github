"""Tiny JSON-backed library of PDFs, transcripts and scripts."""
import json
import threading
import time
import uuid
from pathlib import Path

from .config import LIBRARY_DIR

_INDEX = LIBRARY_DIR / "index.json"
_lock = threading.Lock()


def _load() -> dict:
    if _INDEX.exists():
        return json.loads(_INDEX.read_text("utf-8"))
    return {}


def _save(data: dict) -> None:
    tmp = _INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    tmp.replace(_INDEX)


def add_item(kind: str, title: str, *, text: str = "", file_name: str = "",
             source: str = "", meta: dict | None = None) -> dict:
    item_id = uuid.uuid4().hex[:12]
    text_file = ""
    if text:
        text_file = f"{item_id}.txt"
        (LIBRARY_DIR / text_file).write_text(text, "utf-8")
    item = {
        "id": item_id, "kind": kind, "title": title, "file": file_name,
        "text_file": text_file, "source": source, "created": time.time(),
        "meta": meta or {},
    }
    with _lock:
        data = _load()
        data[item_id] = item
        _save(data)
    return item


def list_items() -> list[dict]:
    with _lock:
        return sorted(_load().values(), key=lambda i: i["created"], reverse=True)


def get_item(item_id: str) -> dict | None:
    with _lock:
        return _load().get(item_id)


def update_item(item_id: str, **fields) -> dict | None:
    with _lock:
        data = _load()
        if item_id not in data:
            return None
        data[item_id].update(fields)
        _save(data)
        return data[item_id]


def set_text(item_id: str, text: str) -> None:
    item = get_item(item_id)
    if not item:
        raise KeyError(item_id)
    name = item.get("text_file") or f"{item_id}.txt"
    (LIBRARY_DIR / name).write_text(text, "utf-8")
    update_item(item_id, text_file=name)


def get_text(item_id: str) -> str:
    item = get_item(item_id)
    if not item or not item.get("text_file"):
        return ""
    p = LIBRARY_DIR / item["text_file"]
    return p.read_text("utf-8") if p.exists() else ""


def file_path(item: dict) -> Path | None:
    return LIBRARY_DIR / item["file"] if item.get("file") else None


def delete_item(item_id: str) -> bool:
    with _lock:
        data = _load()
        item = data.pop(item_id, None)
        if not item:
            return False
        for key in ("file", "text_file"):
            if item.get(key):
                (LIBRARY_DIR / item[key]).unlink(missing_ok=True)
        _save(data)
        return True
