import os
import pathlib
# Make the top‑level ``app`` package point to the actual implementation under ``api/app``.
_module_dir = pathlib.Path(__file__).resolve().parent.parent / 'api' / 'app'
if _module_dir.is_dir():
    __path__.append(str(_module_dir))
