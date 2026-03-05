# UDM_OS/app/logs.py
import json, time
from pathlib import Path
from .config_layer import get as cfg_get

def _events_path():
    cfg = cfg_get() or {}
    p = (cfg.get("logging") or {}).get("events_path") or "UDM_OS/var/udm/events/log.jsonl"
    return Path(p)

def log_event(kind: str, data: dict):
    p = _events_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": int(time.time()), "kind": kind, "data": data or {}}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def tail(lines: int = 200):
    p = _events_path()
    if not p.exists(): return []
    buf = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            buf.append(line.strip())
    return buf[-max(1, lines):]
