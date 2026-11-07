import os, pathlib
# Set a safe temporary directory for pytest on Windows where the default temp may be restricted.
os.environ.setdefault('PYTEST_TMPDIR', str(pathlib.Path(__file__).resolve().parent / 'tmp'))
os.environ.setdefault('TMPDIR', str(pathlib.Path(__file__).resolve().parent / 'tmp'))
os.environ.setdefault('TEMP', str(pathlib.Path(__file__).resolve().parent / 'tmp'))
os.environ.setdefault('TMP', str(pathlib.Path(__file__).resolve().parent / 'tmp'))
