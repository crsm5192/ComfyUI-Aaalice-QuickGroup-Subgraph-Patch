"""Run upstream and subgraph regression tests on a temporary patched package."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    target = patch.target_path(args.target)
    with tempfile.TemporaryDirectory(prefix="aaalice-subgraph-test-") as temporary:
        copy = Path(temporary)
        (copy / "js/lib").mkdir(parents=True)
        (copy / "tests").mkdir()
        (copy / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        for name in [patch.RUNTIME, patch.NAVIGATION, "js/lib/graph_scope.js", "js/lib/quick_group_manager_model.js"]:
            shutil.copyfile(target / name, copy / name)
        tests = []
        for name in ["quick_group_manager_runtime.test.js", "quick_group_manager_model.test.js", "group_navigation.test.js"]:
            shutil.copyfile(target / "tests" / name, copy / "tests" / name)
            tests.append(str(copy / "tests" / name))
        shutil.copyfile(PROJECT / "tests/runtime_subgraphs.test.js", copy / "tests/runtime_subgraphs.test.js")
        tests.append(str(copy / "tests/runtime_subgraphs.test.js"))
        patch.install(copy)
        result = subprocess.run(["node", "--test", *tests], cwd=copy)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
