from __future__ import annotations


class SyncError(Exception):
    """Base exception for repository sync and change-detection failures."""


class GitNotFoundError(SyncError):
    """Raised when the git executable is not available."""


class NotAGitRepositoryError(SyncError):
    """Raised when the target path is not inside a git work tree."""


class NoChangesError(SyncError):
    """Raised when no relevant TypeScript changes are detected."""