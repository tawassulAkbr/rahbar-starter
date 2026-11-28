"""Generate the submission PDF from the evidence-based HTML report."""
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
html_path = ROOT / 'docs' / 'Assignment_03_Report.html'
pdf_path = ROOT / 'docs' / 'Assignment_03_Report.pdf'

if not html_path.exists():
    print(f'HTML report not found: {html_path}', file=sys.stderr)
    sys.exit(1)

browser = shutil.which('msedge') or shutil.which('chromium') or shutil.which('google-chrome')
if not browser:
    edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
    if edge.exists():
        browser = str(edge)

if browser:
    temporary_pdf = pdf_path.with_name('Assignment_03_Report.tmp.pdf')
    temporary_pdf.unlink(missing_ok=True)
    subprocess.run([
        browser, '--headless', '--disable-gpu', '--no-pdf-header-footer',
        f'--user-data-dir={ROOT / ".audit-data" / "pdf-browser"}',
        f'--print-to-pdf={temporary_pdf}', html_path.as_uri(),
    ], check=True, timeout=120)
    for _ in range(50):
        if temporary_pdf.exists() and temporary_pdf.stat().st_size > 0:
            break
        time.sleep(0.2)
    else:
        sys.exit('Browser exited without creating a PDF')
    temporary_pdf.replace(pdf_path)
else:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        sys.exit(f'No working PDF renderer found: {exc}')
    HTML(str(html_path)).write_pdf(str(pdf_path))
print('PDF generated at', pdf_path)
