from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from forgeagentcoder.data.trajectory_export import export_trajectory_dataset


def main() -> None:
    trajectory_json = PROJECT_ROOT / "results" / "local" / "toy_self_repair_v0" / "trajectory.json"
    output_dir = PROJECT_ROOT / "results" / "local" / "trajectory_dataset_v0" / "toy_self_repair_v0"

    if not trajectory_json.exists():
        raise SystemExit(
            f"Missing trajectory file: {trajectory_json}. "
            "Run scripts/dev/run_toy_self_repair.py first."
        )

    summary = export_trajectory_dataset(
        trajectory_json=trajectory_json,
        output_dir=output_dir,
    )

    print(json.dumps(summary, indent=2))

    if summary["total_attempts"] != 2:
        raise SystemExit("Expected 2 total attempts")
    if summary["positive_attempts"] != 1:
        raise SystemExit("Expected 1 positive attempt")
    if summary["negative_attempts"] != 1:
        raise SystemExit("Expected 1 negative attempt")
    if summary["best_patch_id"] != "good_patch_multiplication":
        raise SystemExit(f"Unexpected best_patch_id: {summary['best_patch_id']}")

    print("TOY_TRAJECTORY_DATASET_EXPORT_OK")


if __name__ == "__main__":
    main()
