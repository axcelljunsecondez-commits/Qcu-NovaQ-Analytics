"""Generate browser defaults from the validated backend configuration."""

import json
from pathlib import Path

from backend.api.optimization import OptimizeRequest
from backend.api.simulation import McRequest


def main():
    root = Path(__file__).resolve().parents[1] / "frontend" / "src" / "api"
    planning = OptimizeRequest(segment={"lambda": 0, "mu": 1, "c": 1}).model_dump(exclude={"segment"})
    simulation = McRequest(segments=[]).model_dump(exclude={"segments"})
    for name, values in [("planning-defaults", planning), ("simulation-defaults", simulation)]:
        (root / f"{name}.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
