from . import registry
from .builtin import DefaultDriver
from .emergent import EmergentDriver
from .registry import register, set_active, active_id, compute, list_drivers, get, compute_with

# Register default driver at import so it is available
register(DefaultDriver())

__all__ = [
    "registry", "DefaultDriver", "EmergentDriver",
    "register", "set_active", "active_id", "compute",
    "list_drivers", "get", "compute_with",
]
