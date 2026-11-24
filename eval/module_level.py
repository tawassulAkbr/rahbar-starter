"""Module-level embedding quality checks for Phase 2."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.request
from pathlib import Path

from metrics import average, cosine

PARAPHRASE_PAIRS = [
    ("What attendance percentage is required?", "How much attendance must a student maintain?"),
    ("When is a student placed on academic warning?", "What CGPA causes an academic warning?"),
    ("What is the normal course load?", "How many courses can a student take in a regular semester?"),
    ("Can a student register for FYP-I?", "What must be completed before FYP-I registration?"),
    ("Is the withdrawal fee refunded?", "Do students get their course fee back after withdrawing?"),
    ("How long is a bachelor's degree?", "What is the minimum duration of an undergraduate degree?"),
    ("Which grade is used after repeating a course?", "How does repeating a course affect CGPA?"),
    ("What is the tuition per credit hour?", "How much does each undergraduate credit hour cost?"),
    ("What happens after three academic warnings?", "What is the consequence of repeated academic warnings?"),
    ("Who can repeat a passed course?", "What are the eligibility rules for grade improvement?"),
    ("What is the current academic-warning threshold?", "Which CGPA avoids academic warning in the current handbook?"),
    ("How often is an access review required?", "At what interval must access permissions be reviewed?"),
    ("How long are records retained?", "What is the records retention period?"),
    ("What approval is needed below the attendance threshold?", "Which authorization is required for low attendance?"),
    ("What semester does the newer policy take effect?", "When does the updated policy become effective?"),
]

UNRELATED_PAIRS = [
    ("What attendance percentage is required?", "How do I reserve a sports facility?"),
    ("When is a student placed on academic warning?", "What is the campus parking permit process?"),
    ("What is the normal course load?", "How do I reset my library account password?"),
    ("Can a student register for FYP-I?", "Where is the student health clinic located?"),
    ("Is the withdrawal fee refunded?", "What is the cafeteria opening schedule?"),
    ("How long is a bachelor's degree?", "How do I apply for a student locker?"),
    ("Which grade is used after repeating a course?", "What is the bus route for visitors?"),
    ("What is the tuition per credit hour?", "How can I join the university football team?"),
    ("What happens after three academic warnings?", "Where can I report a lost identity card?"),
    ("Who can repeat a passed course?", "What documents are needed for hostel allocation?"),
    ("What is the current academic-warning threshold?", "When is the next graduation ceremony?"),
    ("How often is an access review required?", "What meals are available in the dining hall?"),
    ("How long are records retained?", "How do I book an auditorium?"),
    ("What approval is needed below the attendance threshold?", "What is the student society registration fee?"),
    ("What semester does the newer policy take effect?", "How can I request a transport pass?"),
]


class DeterministicEmbedder:
    provider = "deterministic-hash-v1"

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def __call__(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class OllamaEmbedder:
    provider = "ollama"

    def __init__(self, endpoint: str, model: str) -> None:
        self.endpoint = endpoint.rstrip("/") + "/api/embed"
        self.model = model

    def __call__(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(self.endpoint, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError("embedding service returned an invalid batch")
        return [[float(value) for value in vector] for vector in embeddings]


def run_module_level(embedder: object | None = None, seed: int = 2026) -> dict[str, object]:
    # The module fixture order is fixed; retain the seed in the result contract.
    embed = embedder or DeterministicEmbedder()
    paraphrases = [pair for pair in PARAPHRASE_PAIRS]
    unrelated = [pair for pair in UNRELATED_PAIRS]
    texts = [text for pair in paraphrases + unrelated for text in pair]
    started = time.perf_counter()
    vectors = embed(texts)
    elapsed = time.perf_counter() - started
    paraphrase_scores = [cosine(vectors[index], vectors[index + 1]) for index in range(0, len(paraphrases) * 2, 2)]
    offset = len(paraphrases) * 2
    unrelated_scores = [cosine(vectors[offset + index], vectors[offset + index + 1]) for index in range(0, len(unrelated) * 2, 2)]
    repeated = embed([paraphrases[0][0], paraphrases[0][0]])
    largest_difference = max(abs(a - b) for a, b in zip(repeated[0], repeated[1]))
    return {
        "level": "module_embedding",
        "seed": seed,
        "provider": getattr(embed, "provider", type(embed).__name__),
        "paraphrase_pairs": len(paraphrases),
        "unrelated_pairs": len(unrelated),
        "mean_paraphrase_cosine": average(paraphrase_scores),
        "mean_unrelated_cosine": average(unrelated_scores),
        "paraphrase_unrelated_gap": (average(paraphrase_scores) or 0.0) - (average(unrelated_scores) or 0.0),
        "embedding_time_ms_per_text": (elapsed * 1000 / len(texts)) if texts else 0.0,
        "determinism_largest_abs_difference": largest_difference,
        "determinism_pass": largest_difference <= 1e-12,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 module-level embedding checks")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--ollama-url")
    parser.add_argument("--model", default="nomic-embed-text")
    args = parser.parse_args()
    embedder = OllamaEmbedder(args.ollama_url, args.model) if args.ollama_url else None
    result = run_module_level(embedder)
    rendered = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
