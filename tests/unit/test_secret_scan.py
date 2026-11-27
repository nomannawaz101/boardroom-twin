from scripts import secret_scan

# Fake secrets are assembled at run time so this file never trips the scan itself.
FAKE_SK_KEY = "sk-" + "a1B2" * 8
FAKE_GOOGLE_KEY = "AI" + "za" + "x" * 35


def rules(text: str, terms: list[str] | None = None, values: list[str] | None = None) -> set[str]:
    return {f.rule for f in secret_scan.scan_text("f.py", text, terms or [], values or [])}


def test_clean_text_has_no_findings() -> None:
    assert rules("print the product name") == set()


def test_sk_key_is_found() -> None:
    assert "api key (sk-)" in rules(f"key = {FAKE_SK_KEY}")


def test_google_key_is_found() -> None:
    assert "google api key" in rules(FAKE_GOOGLE_KEY)


def test_quoted_secret_assignment_is_found() -> None:
    assert "secret assignment" in rules('API_KEY = "' + "q" * 20 + '"')


def test_private_term_matches_any_case() -> None:
    assert "private term" in rules("built for ACMECORP", terms=["AcmeCorp"])


def test_env_value_is_found() -> None:
    assert "value from .env.local" in rules("url=https://gw.internal", values=["gw.internal"])


def test_plan_and_env_files_must_not_be_tracked() -> None:
    found = secret_scan.forbidden_files(["PLAN.md", "docs/a.md", ".env.local"])
    assert [f.path for f in found] == ["PLAN.md", ".env.local"]


def test_finding_never_holds_the_matched_value() -> None:
    found = secret_scan.scan_text("f.py", FAKE_SK_KEY, [], [])
    assert all(FAKE_SK_KEY not in str(f) for f in found)
