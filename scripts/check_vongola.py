"""Offline adapter validation and explicitly synthetic fixture checks; no model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import tomllib

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("chrome", "hayato", "kyoya")


def configuration_checks() -> dict[str, Any]:
    # PyYAML is already available in the repository development environment.
    # Do not silently install a parser or substitute regex parsing for valid YAML.
    import yaml

    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool) -> None:
        checks.append({"check": name, "passed": bool(passed)})

    for platform, extension in (("codex", "toml"), ("claude", "md")):
        directory = ROOT / f".{platform}" / "agents"
        files = sorted(directory.glob(f"*.{extension}"))
        check(f"{platform}: exactly three declarations", len(files) == 3)
        names = []
        for file in files:
            text = file.read_text(encoding="utf-8")
            if platform == "codex":
                data = tomllib.loads(text)
                body = data.get("developer_instructions", "")
                check(f"{file.name}: supported adapter keys", set(data) == {
                    "name", "description", "developer_instructions", "features"
                })
                check(f"{file.name}: external tools reduced", data.get("features") == {
                    "apps": False, "plugins": False
                })
            else:
                parts = text.split("---\n", 2)
                if len(parts) != 3 or parts[0]:
                    raise ValueError(f"Invalid frontmatter delimiters: {file}")
                data = yaml.safe_load(parts[1])
                body = parts[2]
                check(f"{file.name}: supported frontmatter keys", set(data) <= {
                    "name", "description", "tools", "model", "memory", "permissionMode"
                })
                check(f"{file.name}: shell retained", "Bash" in data.get("tools", ""))
                role = data.get("name")
                check(f"{file.name}: retained model", data.get("model") == (
                    "opus" if role == "chrome" else "inherit"
                ))
                check(f"{file.name}: retained memory", data.get("memory") == (
                    None if role == "chrome" else "project"
                ))
            name = data.get("name")
            names.append(name)
            check(f"{file.name}: identity matches filename", name == file.stem)
            check(f"{file.name}: description", bool(data.get("description")))
            check(f"{file.name}: shared authority", "AGENTS.md" in body)
            check(f"{file.name}: shared role", f"docs/agents/{name}.md" in body)
            check(f"{file.name}: preflight", "preflight" in body.lower())
            check(f"{file.name}: reference exists", (ROOT / f"docs/agents/{name}.md").is_file())
        check(f"{platform}: unique roster", sorted(names) == list(ROLES))

    project = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    check("Codex agents enabled", project.get("agents", {}).get("enabled") is True)
    check("Claude shared import", "\n@AGENTS.md\n" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    permissions = settings.get("permissions", {})
    check("Claude no new allow rules", "allow" not in permissions)
    check("Claude mutation prompts", all(
        f"{shell}(git {operation} *)" in permissions.get("ask", [])
        for shell in ("Bash", "PowerShell")
        for operation in ("add", "commit", "push", "merge", "reset", "clean")
    ))
    check("Claude secret file rules", "Read(//**/.env)" in permissions.get("deny", []))
    check("Codex command rule exists", (ROOT / ".codex/rules/vongola.rules").is_file())
    return {"kind": "static_configuration", "checks": checks,
            "passed": all(item["passed"] for item in checks),
            "native_loading": "NOT TESTED", "permission_runtime": "NOT TESTED"}


def fixture_checks(file: Path, kind: str) -> dict[str, Any]:
    """Execute only an explicitly selected, trusted synthetic fixture copy."""
    source = file.read_bytes()
    namespace: dict[str, Any] = {}
    fixture_builtins = {"str": str, "int": int, "list": list, "sum": sum}
    # Restricted builtins reduce accidental use; this is not a security sandbox.
    exec(compile(source, str(file), "exec"), {"__builtins__": fixture_builtins}, namespace)
    if kind == "labels":
        function = namespace["normalize_label"]
        cases: list[tuple[Any, Any]] = [
            ("  NovaQ  ", "NovaQ"), ("  a  B  ", "a  B"), ("", ""), ("   ", "")
        ]
    else:
        function = namespace["total"]
        cases = [([], 0), ([2, 3, 5], 10), ([7], 7), ([-2, 4], 2)]
    results = []
    for value, expected in cases:
        actual = function(value)
        results.append({"input": value, "expected": expected, "actual": actual,
                        "passed": actual == expected})
    return {"kind": f"synthetic_{kind}", "file": str(file.resolve()),
            "sha256": hashlib.sha256(source).hexdigest(), "cases": results,
            "passed": all(item["passed"] for item in results)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--labels", type=Path)
    group.add_argument("--total", type=Path)
    args = parser.parse_args()
    try:
        if args.labels or args.total:
            result = fixture_checks(args.labels or args.total, "labels" if args.labels else "total")
        else:
            result = configuration_checks()
    except (OSError, ValueError, ImportError, KeyError, TypeError, SyntaxError) as error:
        print(json.dumps({"status": "INCONCLUSIVE", "error": str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
