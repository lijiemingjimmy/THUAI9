from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a PvE official_evaluator submission directory.")
    parser.add_argument("--model", required=True, help="Path to trained model.pt")
    parser.add_argument("--output", default="submission/our_agent")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(here / "agent.py", output / "agent.py")
    shutil.copy2(args.model, output / "model.pt")
    print(f"[submission] wrote {output}")


if __name__ == "__main__":
    main()
