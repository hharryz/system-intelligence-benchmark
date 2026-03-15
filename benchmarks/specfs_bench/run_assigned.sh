#!/usr/bin/env bash

set -euo pipefail

MODEL_NAME="${1:-openai/qwen-plus}"
JUDGE_MODEL_NAME="${2:-$MODEL_NAME}"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -d ".venv" ]]; then
  # Use benchmark-local virtual env when available.
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

SAFE_MODEL="${MODEL_NAME//\//_}"
SAFE_JUDGE="${JUDGE_MODEL_NAME//\//_}"

MODULES=("file" "inode" "interface-util")

echo "==> Running assigned SpecFS modules"
echo "==> Model: ${MODEL_NAME}"
echo "==> Judge: ${JUDGE_MODEL_NAME}"
echo "==> Timestamp: ${TIMESTAMP}"

for module in "${MODULES[@]}"; do
  out_dir="outputs/${module}__${SAFE_MODEL}__judge_${SAFE_JUDGE}__${TIMESTAMP}"
  echo ""
  echo "==> [${module}] output: ${out_dir}"
  python src/main.py \
	--model_name "${MODEL_NAME}" \
	--judge_model_name "${JUDGE_MODEL_NAME}" \
	--spec_dir "data/spec/${module}" \
	--code_dir "data/code" \
	-o "${out_dir}"
done

echo ""
echo "==> Summary"
python3 - "$TIMESTAMP" <<'PY'
import json
import pathlib
import sys

ts = sys.argv[1]
root = pathlib.Path("outputs")
modules = ["file", "inode", "interface-util"]

header = (
	f"{'module':<16} {'specs':>5} {'gen_ok':>6} {'judged':>6} "
	f"{'missing_gt':>10} {'avg10':>8} {'avg100':>8}"
)
print(header)
print("-" * len(header))

for module in modules:
	matches = sorted(root.glob(f"{module}__*__{ts}/summary.json"))
	if not matches:
		print(f"{module:<16} {'-':>5} {'-':>6} {'-':>6} {'-':>10} {'-':>8} {'-':>8}")
		continue

	with matches[-1].open("r", encoding="utf-8") as f:
		data = json.load(f)

	gen = data.get("generation", {})
	judge = data.get("judge", {})
	print(
		f"{module:<16} "
		f"{gen.get('total_specs', 0):>5} "
		f"{gen.get('success_count', 0):>6} "
		f"{judge.get('judged_count', 0):>6} "
		f"{judge.get('missing_ground_truth_count', 0):>10} "
		f"{judge.get('avg_score_10', 0):>8} "
		f"{judge.get('avg_score_100', 0):>8}"
	)
PY

echo ""
echo "Done. Outputs are under ./outputs/"
