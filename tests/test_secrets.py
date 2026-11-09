import dataclasses

import pytest

from agent_cairn.secrets import Finding, scan

# Built by concatenation so the repository itself never contains a literal secret.
POSITIVE = {
    "private-key": "-----BEGIN RSA " + "PRIVATE KEY-----",
    "aws-access-key": "key AKIA" + "ABCDEFGHIJKLMNOP here",
    "github-token": "ghp_" + "a" * 36,
    "slack-token": "xoxb-" + "1234567890-abc",
    "openai-key": "sk-proj-" + "A" * 24,
    "anthropic-key": "sk-ant-" + "api03-" + "B" * 24,
    "jwt": "eyJ" + "hbGciOiJIUzI1" + "." + "eyJzdWIiOiIx" + "." + "SflKxwRJSMeK",
    "assignment": "password = " + "hunter2hunter2",
}

NEAR_MISSES = [
    "AKIA1234",  # too short for an access key
    "ghp_short",
    "sk-ant",
    "the token is stored in the keychain",
    "password = <your-password>",
    "api_key: ${API_KEY}",
    "secret = ********",
    "token = xxxxxxxxxxxx",
    "password: changeme",
    "access_key = example-key-value",
]


@pytest.mark.req("R12.1")
@pytest.mark.parametrize(("pattern", "line"), POSITIVE.items())
def test_scan_detects_each_pattern(pattern, line):
    assert scan(f"intro\n{line}\n") == [Finding(line=2, pattern=pattern)]


@pytest.mark.req("R12.1")
@pytest.mark.parametrize("line", NEAR_MISSES)
def test_scan_ignores_placeholders_and_near_misses(line):
    assert scan(line) == []


@pytest.mark.req("R12.2")
def test_finding_never_holds_the_secret_value():
    (finding,) = scan(POSITIVE["github-token"])

    assert {field.name for field in dataclasses.fields(finding)} == {"line", "pattern"}
    assert "ghp_" not in repr(finding)
