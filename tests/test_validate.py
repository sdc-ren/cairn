import pytest
from conftest import FILLED_BODY

from agent_cairn.constants import CAPTURED_MARKER, MAX_BODY_CHARS
from agent_cairn.validate import Violation, errors, validate


def _rules(body):
    return [violation.rule for violation in errors(validate(body))]


def _warnings(body):
    return [v.rule for v in validate(body) if v.level == "warning"]


@pytest.mark.req("R5.3")
def test_validate_filled_body_passes():
    assert validate(FILLED_BODY) == []


@pytest.mark.req("R5.3")
@pytest.mark.parametrize("first_line", ["", "# ", "# <title>", "# TODO"])
def test_validate_missing_or_placeholder_title_fails(first_line):
    body = FILLED_BODY.replace("# Login form: wire OAuth callback", first_line, 1)

    assert "missing-title" in _rules(body)


@pytest.mark.req("R5.3")
@pytest.mark.req("R2.4")
@pytest.mark.parametrize("section", ["Goal", "Current state", "Next steps"])
def test_validate_missing_required_section_fails(section):
    body = FILLED_BODY.replace(f"## {section}\n", "## Renamed\n")

    assert _rules(body) == ["missing-section"]


@pytest.mark.req("R5.3")
@pytest.mark.parametrize("content", ["", "<!-- describe the goal -->", "TODO", "  tbd  ", "..."])
def test_validate_empty_required_section_fails(content):
    body = FILLED_BODY.replace("Users can sign in with Google.", content)

    assert _rules(body) == ["empty-section"]


@pytest.mark.req("R5.3")
def test_validate_section_names_match_case_insensitively():
    body = FILLED_BODY.replace("## Current state", "## current STATE")

    assert validate(body) == []


@pytest.mark.req("R5.3")
def test_validate_next_steps_without_list_items_fails():
    body = FILLED_BODY.replace(
        "- [ ] Set session cookie\n- [ ] Run `pnpm test:e2e login`", "Set the cookie."
    )

    assert _rules(body) == ["next-steps-no-items"]


@pytest.mark.req("R5.3")
@pytest.mark.parametrize("item", ["- a", "* a", "1. a", "- [ ] a"])
def test_validate_next_steps_accepts_list_styles(item):
    body = FILLED_BODY.replace("- [ ] Set session cookie", item)

    assert validate(body) == []


@pytest.mark.req("R5.3")
def test_validate_next_steps_items_only_inside_comment_fails():
    body = FILLED_BODY.replace(
        "- [ ] Set session cookie\n- [ ] Run `pnpm test:e2e login`", "Do it.\n<!-- - a -->"
    )

    assert _rules(body) == ["next-steps-no-items"]


@pytest.mark.req("R5.3")
def test_validate_body_too_long_fails():
    body = FILLED_BODY + "x" * MAX_BODY_CHARS

    assert _rules(body) == ["body-too-long"]


@pytest.mark.req("R5.3")
def test_validate_reserved_marker_fails():
    body = FILLED_BODY + f"\n{CAPTURED_MARKER}\n"

    assert _rules(body) == ["reserved-marker"]


@pytest.mark.req("R5.4")
def test_violation_formats_with_and_without_line():
    with_line = Violation("empty-section", "fill it in", line=4)

    assert str(with_line) == "line 4: empty-section: fill it in"
    assert str(Violation("missing-section", "add it")) == "missing-section: add it"


@pytest.mark.req("R5.4")
def test_validate_reports_line_of_offending_section():
    body = FILLED_BODY.replace("Users can sign in with Google.", "TODO")

    (violation,) = validate(body)

    assert violation.line == 3


@pytest.mark.req("R5.3")
@pytest.mark.req("R2.5")
def test_validate_missing_recommended_section_is_only_a_warning():
    body = FILLED_BODY.replace("## Decisions", "## Notes")

    assert _rules(body) == []
    assert _warnings(body) == ["missing-recommended"]


@pytest.mark.req("R5.3")
@pytest.mark.parametrize("heading", ["Tried", "Didn't work"])
def test_validate_accepts_tried_section_variants(heading):
    body = FILLED_BODY.replace("## Tried / didn't work", f"## {heading}")

    assert validate(body) == []


@pytest.mark.req("R5.3")
def test_validate_long_body_warns():
    body = FILLED_BODY + "\n" + "y" * 6_100

    assert _warnings(body) == ["body-long"]
