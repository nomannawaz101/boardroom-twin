"""Scan files staged in git for keys and private terms. Runs as the pre-commit hook.

Private terms (company name, gateway host) cannot be written in the repo, so they come from
SECRET_SCAN_TERMS in .env.local. Every value in .env.local is also treated as a secret.
Findings name the file and the rule only; a matched value is never printed.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.local"
TERMS_VAR = "SECRET_SCAN_TERMS"
FORBIDDEN_TRACKED = ("PLAN.md", ".env.local", ".env")
MIN_SECRET_VALUE_LEN = 8
BINARY_PROBE_BYTES = 8000

KEY_PATTERNS: dict[str, re.Pattern[str]] = {
    "api key (sk-)": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "google api key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "github token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "secret assignment": re.compile(
        r"(?i)(api[_-]?key|secret|token|passcode)\s*[:=]\s*['\"][^'\"\s]{16,}['\"]"
    ),
}


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str


def scan_text(
    path: str, text: str, private_terms: list[str], secret_values: list[str]
) -> list[Finding]:
    findings = [
        Finding(path, rule) for rule, pattern in KEY_PATTERNS.items() if pattern.search(text)
    ]
    lowered = text.lower()
    if any(term.lower() in lowered for term in private_terms):
        findings.append(Finding(path, "private term"))
    if any(value in text for value in secret_values):
        findings.append(Finding(path, "value from .env.local"))
    return findings


def forbidden_files(paths: list[str]) -> list[Finding]:
    return [
        Finding(p, "file must never be tracked") for p in paths if Path(p).name in FORBIDDEN_TRACKED
    ]


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True).stdout


def staged_paths() -> list[str]:
    return [p for p in git("ls-files", "-z", "--cached").decode().split("\0") if p]


def staged_text(path: str) -> str | None:
    """Content as staged (what the commit will hold); None for binary files."""
    data = git("show", f":{path}")
    if b"\0" in data[:BINARY_PROBE_BYTES]:
        return None
    return data.decode("utf-8", errors="ignore")


def load_private_settings() -> tuple[list[str], list[str]]:
    env = {k: v for k, v in dotenv_values(ENV_FILE).items() if v}
    terms = [t.strip() for t in env.pop(TERMS_VAR, "").split(",") if t.strip()]
    values = [v for v in env.values() if len(v) >= MIN_SECRET_VALUE_LEN]
    return terms, values


def scan_repo() -> tuple[list[Finding], bool]:
    terms, values = load_private_settings()
    paths = staged_paths()
    findings = forbidden_files(paths)
    for path in paths:
        text = staged_text(path)
        if text is not None:
            findings.extend(scan_text(path, text, terms, values))
    return findings, bool(terms)


def main() -> int:
    findings, has_terms = scan_repo()
    if not has_terms:
        sys.stderr.write(f"secret scan: warning, {TERMS_VAR} not set; private terms not checked\n")
    for finding in findings:
        sys.stderr.write(f"secret scan: {finding.path}: {finding.rule}\n")
    sys.stderr.write("secret scan: " + ("FAIL\n" if findings else "clean\n"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
