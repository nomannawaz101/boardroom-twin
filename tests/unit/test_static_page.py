"""The page must agree with the server and stay plain: no innerHTML, no CDN, same limits."""

import json
import re

import config
from tests.fixtures import briefs

STATIC = config.PROJECT_ROOT / "static"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
# The one outside link: a plain footer link to the project's source, opened in a new tab. It
# loads nothing into the page.
SOURCE_LINK = "https://github.com/nomannawaz101/boardroom-twin"
HTML_SINKS = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(")


def page_files() -> list[tuple[str, str]]:
    files = [STATIC / "index.html", *sorted((STATIC / "js").glob("*.js"))]
    return [(f.name, f.read_text(encoding="utf-8")) for f in files]


def test_country_options_match_the_server_list() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    select = html.split('id="country"', 1)[1].split("</select>", 1)[0]
    options = re.findall(r"<option[^>]*>([^<]+)</option>", select)
    assert options == list(config.COUNTRIES)


def test_brief_limit_matches_the_server() -> None:
    state_js = (STATIC / "js" / "state.js").read_text(encoding="utf-8")
    assert f"BRIEF_MAX_CHARS = {config.BRIEF_MAX_CHARS}" in state_js


def test_no_html_sinks_anywhere_in_the_page_code() -> None:
    for name, text in page_files():
        for sink in HTML_SINKS:
            assert sink not in text, f"{sink} found in {name}"


def test_no_cdn_or_outside_urls() -> None:
    for name, text in page_files() + [("style.css", (STATIC / "css" / "style.css").read_text())]:
        urls = set(re.findall(r"https?://[^\s\"')]+", text)) - {SVG_NAMESPACE, SOURCE_LINK}
        assert not urls, f"outside URL in {name}: {urls}"


def test_sample_buttons_carry_the_appendix_b_briefs_and_valid_countries() -> None:
    samples = json.loads((STATIC / "sample" / "briefs.json").read_text(encoding="utf-8"))
    assert [s["brief"] for s in samples] == list(briefs.SAMPLE_BRIEFS)
    assert all(s["country"] in config.COUNTRIES for s in samples)


def test_stage_cost_is_labelled_as_an_estimate() -> None:
    render_js = (STATIC / "js" / "render.js").read_text(encoding="utf-8")
    assert "toFixed(2)} est.`" in render_js
