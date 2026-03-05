from typing import Dict, Tuple, Protocol

class Driver(Protocol):
    id: str
    version: str
    def compute(self, signals: Dict) -> Tuple[float, float, float]: ...
