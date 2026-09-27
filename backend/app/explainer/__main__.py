"""CLI: python -m app.explainer brief.json --out workdir [--storyboard sb.json] [--script-only]"""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run_explainer
from .schema import Brief
from .writer import write_storyboard


def main() -> int:
    ap = argparse.ArgumentParser(description="Moteur Pub explicative CutForge")
    ap.add_argument("brief")
    ap.add_argument("--out", required=True)
    ap.add_argument("--storyboard")
    ap.add_argument("--script-only", action="store_true")
    ap.add_argument("--workers", type=int)
    a = ap.parse_args()
    brief = json.load(open(a.brief, encoding="utf-8"))
    if a.script_only:
        print(json.dumps(write_storyboard(Brief.from_dict(brief)).to_dict(), ensure_ascii=False, indent=1))
        return 0
    sb = json.load(open(a.storyboard, encoding="utf-8")) if a.storyboard else None
    res = run_explainer(brief, a.out, storyboard=sb, workers=a.workers,
                        progress=lambda p, m: print(f"[{p:3d}%] {m}", file=sys.stderr, flush=True))
    print(json.dumps({k: v for k, v in res.items() if k != "storyboard"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
