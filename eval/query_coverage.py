"""Measure vocabulary coverage of the simulated query log against golden questions."""
import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


def read(name):
    return [json.loads(line) for line in Path(name).read_text(encoding="utf-8").splitlines() if line.strip()]


def vector(question):
    stop = set("a an the is are do does can what which i we my for and in on of to how from at me it under".split())
    counts = Counter(t.removesuffix("s") for t in re.findall(r"[a-z0-9]+", question.lower()) if t not in stop)
    norm = math.sqrt(sum(n*n for n in counts.values()))
    return {t: n/norm for t, n in counts.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    golden = read("eval/golden.jsonl")
    if args.expanded:
        golden.extend(read("eval/coverage_additions.jsonl"))
    index = [(row, vector(row["question"])) for row in golden]
    matches = []
    gaps = defaultdict(list)
    for live in read("eval/live_queries.jsonl"):
        query = vector(live["question"])
        score, nearest = max(((sum(w * v.get(t, 0) for t, w in query.items()), row)
                              for row, v in index), key=lambda pair: pair[0])
        matches.append({**live, "nearest_id": nearest["id"], "nearest_question": nearest["question"], "cosine": score})
        if score < 0.40:
            gaps[live["topic"]].append(live["id"])
    share = 1 - sum(map(len, gaps.values())) / len(matches)
    result = {"method": "cosine of normalized content-word counts", "similarity_min": 0.40,
              "coverage_min": 0.85, "golden_count": len(golden), "share": share,
              "uncovered_by_topic": gaps, "matches": matches}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{len(golden)} golden questions: {share:.1%} coverage (minimum 85%)")
    return int(share < 0.85)


if __name__ == "__main__":
    raise SystemExit(main())
