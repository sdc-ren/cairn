"""Expected failures; each class carries the process exit code it maps to (R17.5)."""

from __future__ import annotations


class CairnError(Exception):
    """An expected failure, reported as one line plus optional detail lines."""

    exit_code = 1

    def __init__(self, message: str, details: tuple[str, ...] = ()) -> None:
        """Store ``details``: extra stderr lines printed verbatim after the message."""
        super().__init__(message)
        self.details = details


class UsageError(CairnError):
    """The command line is invalid."""

    exit_code = 2


class InvalidHandoffError(CairnError):
    """A handoff body or file does not follow the required format."""

    exit_code = 3


class NotFoundError(CairnError):
    """No handoff matches the request."""

    exit_code = 4


class NotAGitRepoError(CairnError):
    """The command needs a git repository but none was found."""

    exit_code = 5
