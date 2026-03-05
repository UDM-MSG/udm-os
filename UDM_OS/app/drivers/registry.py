import os, importlib.util, sys
from typing import Dict, Tuple, Optional
from pathlib import Path
from .builtin import DefaultDriver
from .base import Driver
try:
    from .emergent import EmergentDriver
except Exception:
    EmergentDriver = None

_registry: Dict[str, Driver] = {}
_active_id: str = os.getenv("UDM_DRIVER_ACTIVE", "default")

def register(driver: Driver):
    _registry[getattr(driver, "id", "unknown")] = driver

def list_drivers():
    return list(_registry.keys())

def get(driver_id: str) -> Optional[Driver]:
    return _registry.get(driver_id)

def set_active(driver_id: str):
    global _active_id
    if driver_id in _registry:
        _active_id = driver_id
    else:
        raise ValueError(f"Driver '{driver_id}' not registered")

def active_id() -> str:
    return _active_id

def _ensure_defaults():
    if not _registry:
        register(DefaultDriver())
        if EmergentDriver is not None:
            try:
                register(EmergentDriver())
            except Exception:
                pass
        _load_external_plugins()

def _load_external_plugins():
    # Load drivers from UDM_OS/opt/udm/drivers/*.py
    root = Path(__file__).resolve().parents[2] / "opt" / "udm" / "drivers"
    if not root.exists(): return
    sys.path.insert(0, str(root))
    for f in root.glob("*.py"):
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name in dir(mod):
                obj = getattr(mod, name)
                if hasattr(obj, "compute") and hasattr(obj, "id") and hasattr(obj, "version"):
                    register(obj())
        except Exception:
            continue

def compute(signals: Dict) -> Tuple[float, float, float]:
    _ensure_defaults()
    d = _registry.get(_active_id) or _registry.get("default") or DefaultDriver()
    return d.compute(signals)

def compute_with(signals: Dict, driver_id: str) -> Tuple[float, float, float]:
    _ensure_defaults()
    d = _registry.get(driver_id)
    if not d:
        d = _registry.get("default") or DefaultDriver()
    return d.compute(signals)
