from dataclasses import dataclass
from typing import *

# ---------- Model returned by analyzer ----------
@dataclass
class UmlModel:
    elements: Dict[str, Dict[str,Any]]
    associations: List[Dict[str,Any]]
    dependencies: List[Tuple[str,str]]
    generalizations: List[Tuple[str,str]]
    name_to_xmi: Dict[str,str]

