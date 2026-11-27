"""Seed a persistent corpus once; subsequent runs preserve deletions/updates."""
import os
import shutil
from pathlib import Path

source = Path('/corpus')
destination = Path(os.environ.get('CORPUS_DIR', '/data/corpus'))
marker = destination.parent / '.corpus-seeded'
if not marker.exists():
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
    marker.write_text('Seeded from image; updates are owned by ingestion.\n')

# Older images seeded only the committed PDFs. Add the fetched source lake
# once when upgrading, preserving subsequent document updates and deletions.
if (source / 'raw').is_dir() and not (destination / 'raw').exists():
    shutil.copytree(source / 'raw', destination / 'raw')
