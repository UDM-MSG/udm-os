# UDM_OS/app/config_layer.py
import os, json
from pathlib import Path
try:
    import yaml
except ImportError:
    yaml = None

CFG_PATH = Path(__file__).resolve().parent.parent / "etc" / "udm" / "config.yaml"

_cache = None

def load():
    global _cache
    try:
        if yaml:
            text = CFG_PATH.read_text(encoding="utf-8")
            _cache = yaml.safe_load(text) or {}
        else:
            _cache = {}
    except Exception:
        _cache = {}
    return _cache

def get():
    global _cache
    return _cache if _cache is not None else load()

def get_path():
    return str(CFG_PATH)
