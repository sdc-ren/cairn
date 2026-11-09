import pytest
from conftest import make_handoff

from agent_cairn import document
from agent_cairn.constants import CAPTURED_MARKER
from agent_cairn.errors import InvalidHandoffError


@pytest.mark.req("R2.1")
def test_render_orders_frontmatter_body_captured():
    text = document.render(make_handoff(id="20261109-083012-main"))

    assert text.startswith("---\nid: 20261109-083012-main\nschema: 1\n")
    assert text.index("# Login form") < text.index(CAPTURED_MARKER) < text.index("## Captured")


@pytest.mark.req("R2.9")
@pytest.mark.parametrize(
    "title",
    ['Login form: wire "OAuth" callback', "  padded  ", "#hash", "Fix: a # b", "tiếng Việt"],
)
def test_parse_render_round_trips_awkward_titles(title):
    handoff = make_handoff(id="x", title=title)

    assert document.parse(document.render(handoff)) == handoff


@pytest.mark.req("R2.9")
def test_parse_render_round_trips_unknown_keys_and_ints():
    handoff = make_handoff(id="x", resume_count=2, resumed_at="2026-11-10T01:00:00Z", extra="v")

    parsed = document.parse(document.render(handoff))

    assert parsed == handoff
    assert parsed.meta["resume_count"] == 2
    assert list(parsed.meta)[-1] == "extra"


@pytest.mark.req("R2.2")
def test_render_writes_plain_values_unquoted():
    text = document.render(make_handoff(id="x"))

    assert "\ncreated_at: 2026-11-09T08:30:12Z\n" in text
    assert "\nbranch: main\n" in text
    assert '\ntitle: "Login form: wire OAuth callback"\n' in text


@pytest.mark.req("R2.1")
@pytest.mark.parametrize(
    "text",
    ["# no frontmatter\n", "---\nid: x\n# never closed\n", "---\nnot a key line\n---\nbody\n"],
)
def test_parse_broken_file_raises_with_source(text):
    with pytest.raises(InvalidHandoffError, match=r"broken\.md"):
        document.parse(text, source="broken.md")


def test_replace_meta_keeps_body_and_captured_bytes():
    text = document.render(make_handoff(id="x")) + "\n  trailing  \n"

    updated = document.replace_meta(text, {"id": "x", "status": "resumed"})

    assert updated.startswith("---\nid: x\nstatus: resumed\n---\n")
    assert updated.endswith(text.split("\n---\n", 1)[1])


def test_sections_ignore_headings_inside_code_fences():
    body = "# T\n\n## Goal\n```\n## Not a section\n```\n\n## Next steps\n- a\n"

    names = [section.name for section in document.sections(body)]

    assert names == ["Goal", "Next steps"]


def test_title_returns_first_h1_with_line():
    assert document.title("\n# Hello\n# Other\n") == (2, "Hello")
