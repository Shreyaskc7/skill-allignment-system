"""Evaluate the skill extractor against the hand-labelled synthetic set in data/.

    python scripts/evaluate_extractor.py            # prints a report
    python scripts/evaluate_extractor.py --json     # machine-readable

Reports micro-averaged precision / recall / F1 for skill detection (required +
optional together) for the version 1 baseline and the current extractor, plus the
accuracy of the required-vs-optional label on correctly detected skills.
The set is small and synthetic: treat the numbers as a regression check, not as
evidence of real-world performance.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.skill_extraction import DictionaryExtractor, default_terms, v1_extract_skills  # noqa: E402

DATASETS = {"development": ROOT / "data" / "skill_extraction_eval.json",
            "heldout": ROOT / "data" / "skill_extraction_heldout.json"}


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def evaluate(dataset: str = "development") -> dict:
    items = json.loads(DATASETS[dataset].read_text(encoding="utf-8"))["items"]
    ext = DictionaryExtractor(default_terms())
    counts = {"v1": [0, 0, 0], "current": [0, 0, 0]}
    label_right = label_total = 0
    errors = []
    for it in items:
        gold = set(it["required"]) | set(it["optional"])
        for name, pred in (("v1", set(v1_extract_skills(it["text"]))),
                           ("current", {e.skill for e in ext.extract(it["text"])})):
            c = counts[name]
            c[0] += len(pred & gold)
            c[1] += len(pred - gold)
            c[2] += len(gold - pred)
            if name == "current" and pred != gold:
                errors.append({"id": it["id"], "missed": sorted(gold - pred), "extra": sorted(pred - gold)})
        for e in ext.extract(it["text"]):
            if e.skill in gold:
                label_total += 1
                label_right += (e.skill in it["required"]) == e.required
    return {
        "items": len(items),
        "v1_baseline": prf(*counts["v1"]),
        "current": prf(*counts["current"]),
        "required_vs_optional_accuracy": round(label_right / label_total, 3) if label_total else None,
        "errors": errors,
    }


def print_report(dataset: str, report: dict) -> None:
    print(f"\n== {dataset} set: {report['items']} items (synthetic, hand-labelled)")
    for k in ("v1_baseline", "current"):
        m = report[k]
        print(f"{k:12} precision {m['precision']:.3f}  recall {m['recall']:.3f}  F1 {m['f1']:.3f}  "
              f"(tp {m['tp']}, fp {m['fp']}, fn {m['fn']})")
    print(f"required-vs-optional accuracy (current): {report['required_vs_optional_accuracy']}")
    for e in report["errors"]:
        print(f"  item {e['id']}: missed {e['missed']} extra {e['extra']}")


if __name__ == "__main__":
    reports = {name: evaluate(name) for name in DATASETS}
    if "--json" in sys.argv:
        print(json.dumps(reports, indent=2))
    else:
        for name, report in reports.items():
            print_report(name, report)
