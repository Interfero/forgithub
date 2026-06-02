"""Скачать классические PNG смайликов ICQ (slangit mirror) в data/icq_smileys/images/."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icq_smileys" / "images"
BASE = "https://slangit.com/img/sc/icq"

IDS = [
    "smile",
    "winking",
    "sad",
    "big_grin",
    "sticking_tongue_out",
    "lips_are_sealed",
    "crying",
    "devil",
    "uh-oh",
    "yelling",
    "angel",
    "kiss",
    "embarrassed",
    "gross",
    "confused",
    "cool",
    "in_love",
    "sleepy",
    "rolleyes",
    "thumbs_up",
    "rose",
    "heart",
    "beer",
    "cake",
    "camera",
    "flower",
    "sun",
    "moon",
    "music",
    "phone",
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for sid in IDS:
            path = OUT / f"{sid}.png"
            if path.is_file() and path.stat().st_size > 200:
                ok += 1
                continue
            url = f"{BASE}/{sid}.png"
            try:
                r = client.get(url)
                if r.status_code == 200 and len(r.content) > 200:
                    path.write_bytes(r.content)
                    ok += 1
                    print(f"OK {sid}")
                else:
                    print(f"SKIP {sid} {r.status_code}")
            except Exception as e:
                print(f"ERR {sid}: {e}")
    print(f"Done: {ok}/{len(IDS)} in {OUT}")
    return 0 if ok >= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
