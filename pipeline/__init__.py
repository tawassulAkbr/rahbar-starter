import pathlib
_module_dir = pathlib.Path(__file__).resolve().parent.parent / 'indexer' / 'pipeline'
if _module_dir.is_dir():
    __path__ = [str(_module_dir)]
