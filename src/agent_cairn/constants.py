"""Limits, timeouts, names and rule ids shared across modules (CODING_STANDARDS CS-2)."""

GIT_TIMEOUT_SECONDS = 10

# Handoff document (R2)
CAPTURED_MARKER = "<!-- cairn:captured -->"
META_ORDER = (
    "id",
    "schema",
    "created_at",
    "title",
    "status",
    "repo",
    "worktree",
    "branch",
    "head",
    "agent",
    "cairn_version",
    "task",
    "session_id",
    "resumed_at",
    "resume_count",
)
META_INT_KEYS = frozenset({"schema", "resume_count"})
STATUS_OPEN = "open"
STATUS_RESUMED = "resumed"

# Body rules (R5.3)
REQUIRED_SECTIONS = ("Goal", "Current state", "Next steps")
NEXT_STEPS_SECTION = "Next steps"
MAX_BODY_CHARS = 12_000
EMPTY_PLACEHOLDERS = frozenset({"todo", "tbd", "..."})
RULE_MISSING_TITLE = "missing-title"
RULE_MISSING_SECTION = "missing-section"
RULE_EMPTY_SECTION = "empty-section"
RULE_NEXT_STEPS_NO_ITEMS = "next-steps-no-items"
RULE_BODY_TOO_LONG = "body-too-long"
RULE_RESERVED_MARKER = "reserved-marker"
RULE_MISSING_RECOMMENDED = "missing-recommended"
RULE_BODY_LONG = "body-long"
LONG_BODY_CHARS = 6_000
RECOMMENDED_SECTIONS = ("Decisions", "Tried / didn't work", "Open questions", "Key files")
SECTION_ALIASES = {"tried": "tried / didn't work", "didn't work": "tried / didn't work"}
ERROR = "error"
WARNING = "warning"

# Store layout, see R1
HOME_ENV = "CAIRN_HOME"
HOME_DIR_NAME = ".cairn"
PROJECT_FILE_NAME = ".project.json"
PROJECT_HASH_CHARS = 8
HANDOFF_SUFFIX = ".md"
LOCK_FILE_NAME = ".lock"
AGENT_ENV = "CAIRN_AGENT"
UNKNOWN_AGENT = "unknown"
SCHEMA_VERSION = 1
STORE_ENV = "CAIRN_STORE"
KEEP_RESUMED_ENV = "CAIRN_KEEP_RESUMED"
KEEP_RESUMED_DEFAULT = "7d"
KEEP_OPEN_ENV = "CAIRN_KEEP_OPEN"
KEEP_OPEN_DEFAULT = "30d"
MIN_ID_PREFIX = 4
DIR_MODE = 0o700
FILE_MODE = 0o600
SLUG_MAX_CHARS = 40
SLUG_FALLBACK = "branch"

# Capture limits, see R4
MAX_CAPTURED_CHANGES = 50
RECENT_COMMITS = 5
SHORT_SHA_CHARS = 7
CAPTURED_HEADING = "## Captured state (auto-generated — do not edit)"
RULE_CREDENTIAL_PREFIX = "secret-"

# Drift and hook, see R10 and R13
MAX_DRIFT_COMMITS = 10
HOOK_GIT_TIMEOUT_SECONDS = 2
HOOK_ENV = "CAIRN_HOOK"
HOOK_MAX_AGE_ENV = "CAIRN_HOOK_MAX_AGE"
HOOK_MAX_AGE_DEFAULT = "7d"
HOOK_CONTEXT_MAX_CHARS = 9000
HOOK_EVENT_NAME = "SessionStart"
OFF = "off"
NO_GIT_LABEL = "workspace"

# Workspace section, see R4.10 and R10.10
WORKSPACE_SECTION = "Workspace"
RESOURCE_WORKTREE = "worktree"
RESOURCE_PIPELINE = "pipeline"
CAPTURED_JSON_OPEN = "<!-- cairn:captured-json "
CAPTURED_JSON_CLOSE = " -->"

# List, see R6
LIST_DEFAULT_LIMIT = 20
LIST_TITLE_MAX_CHARS = 60
NO_HANDOFFS_MESSAGE = "no handoffs yet"

# GitHub CLI, see R4.4
GH_TIMEOUT_SECONDS = 5
GH_LIMIT = 100
PRS_OK = "ok"
PRS_UNAVAILABLE = "unavailable"
PRS_SKIPPED = "skipped"
TEMPLATE_ASSET = "template.md"

# Doctor and compaction hooks, see R15 and R23
MIN_PYTHON = (3, 9)
MIN_GIT_VERSION = (2, 31)
NUDGE_ENV = "CAIRN_NUDGE"
NUDGE_WINDOW_ENV = "CAIRN_NUDGE_WINDOW"
NUDGE_WINDOW_DEFAULT = "2h"
PRECOMPACT_ASSET = "precompact.md"
NUDGE_ASSET = "nudge.md"

# Other agents, see R21
SKILL_NAMES = ("handoff", "resume")
SKILLS_ASSET = "skills.json"
STANDALONE_SKILL_PREFIX = "cairn-"
MANAGED_MARKER = "<!-- managed-by: cairn v{version} -->"
MANAGED_PREFIX = "<!-- managed-by: cairn "
AGENTS_FILE = "AGENTS.md"
AGENTS_BEGIN = "<!-- cairn:begin -->"
AGENTS_END = "<!-- cairn:end -->"
BACKUP_SUFFIX = ".bak"
CLAUDE_DIR = ".claude"
SKILLS_DIR = "skills"
SKILL_FILE = "SKILL.md"
CLIPBOARD_TIMEOUT_SECONDS = 5
