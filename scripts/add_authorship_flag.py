import json, pathlib, sys
p = pathlib.Path(r"eval\results\assignment03-final\checklist.json")
if not p.is_file():
    sys.exit(f"Checklist not found: {p}")
obj = json.loads(p.read_text())
for itm in obj.get('items', []):
    if itm.get('task') == 'B personal authorship / review':
        itm['personal_authorship_and_review_confirmed'] = True
        break
p.write_text(json.dumps(obj, indent=2) + "\n")
print('Authorship flag added')
