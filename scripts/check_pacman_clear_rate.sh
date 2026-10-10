#!/usr/bin/env bash
# Prepared for the target environment; not executed locally.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUT_DIR="${OUT_DIR:-$PWD/runs/clear-rate-teacher-$(date +%Y%m%d-%H%M%S)-$$}"
mkdir -p "$OUT_DIR"

"$PYTHON_BIN" -m playjev.play pacman --policy teacher  \
  --pages 1 --episodes "${EPISODES:-2}" --max-steps "${MAX_STEPS:-1500}" \
  --seed0 "${SEED0:-5000}" --no-skip-noop \
  --record "$OUT_DIR/replays" --out "$OUT_DIR/result.json" "$@"
"$PYTHON_BIN" - "$OUT_DIR" <<'PYTHON'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
result = json.loads((root / "result.json").read_text())
replays = [json.loads(p.read_text()) for p in (root / "replays/pacman").glob("*.json")]
assert len(replays) == result["episodes"]
assert all(r["cleared"] == (r["max_level"] > r["start_level"]) for r in replays)
assert result["cleared_episodes"] == sum(r["cleared"] for r in replays)
assert result["clear_rate"] == result["cleared_episodes"] / result["episodes"]
print(f"Verified {result['cleared_episodes']}/{result['episodes']} cleared episodes ({result['clear_rate']:.1%}).")
PYTHON
