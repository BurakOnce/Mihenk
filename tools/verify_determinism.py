"""prove that the same seed produces byte-identical output.

claude yardımıyla yazıldı - bu script sayesinde xlsx dosyasının tekrar
üretilebilir olmadığını fark ettim (zip içindeki zaman damgası yüzünden).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def digest_tree(root: Path) -> dict[str, str]:
    """sha-256 per file, keyed by relative path"""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".gitkeep"
    }

def tree_digest(files: dict[str, str]) -> str:
    """one hash for the whole tree, covering names as well as contents"""
    joined = "".join(f"{name}:{files[name]}\n" for name in sorted(files))
    return hashlib.sha256(joined.encode()).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scale", type=float, default=0.05,
        help="volume multiplier; the default is small because this runs the "
             "generator twice and reproducibility does not depend on volume",
    )
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="mihenk_determinism_") as workspace:
        outputs = [Path(workspace) / "run1", Path(workspace) / "run2"]

        for index, output in enumerate(outputs, start=1):
            command = [
                sys.executable, "-m", "data_generator",
                "--scale", str(args.scale),
                "--output", str(output),
                "--clean",
            ]
            if args.seed is not None:
                command += ["--seed", str(args.seed)]

            print(f"run {index} ...", end=" ", flush=True)
            result = subprocess.run(
                command, cwd=REPO_ROOT, capture_output=True, text=True
            )
            if result.returncode != 0:
                print("FAILED")
                print(result.stderr[-3000:])
                return 1
            print("done")

        first, second = digest_tree(outputs[0]), digest_tree(outputs[1])

        only_first = sorted(set(first) - set(second))
        only_second = sorted(set(second) - set(first))
        differing = sorted(k for k in set(first) & set(second) if first[k] != second[k])

        print()
        print(f"  files in run 1   : {len(first):,}")
        print(f"  files in run 2   : {len(second):,}")
        print(f"  only in run 1    : {len(only_first)}")
        print(f"  only in run 2    : {len(only_second)}")
        print(f"  differing content: {len(differing)}")
        print()
        print(f"  run 1 tree digest: {tree_digest(first)}")
        print(f"  run 2 tree digest: {tree_digest(second)}")

        ok = not (only_first or only_second or differing)
        print()
        if ok:
            print("  REPRODUCIBLE - every byte matches.")
            return 0

        print("  NOT REPRODUCIBLE.")
        for name in (only_first + only_second + differing)[:20]:
            print(f"    {name}")

        rescue = REPO_ROOT / "determinism_failure"
        rescue.mkdir(exist_ok=True)
        for name in differing[:5]:
            for index, output in enumerate(outputs, start=1):
                source = output / name
                if source.exists():
                    target = rescue / f"run{index}_{name.replace('/', '_')}"
                    shutil.copy2(source, target)
        print(f"\n  differing files copied to {rescue.relative_to(REPO_ROOT)}/")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
