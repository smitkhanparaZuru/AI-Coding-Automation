from __future__ import annotations

import subprocess

from aica.core.logging import get_logger
from aica.execution.runner import RunResult

_LOG_TRUNCATE = 500

log = get_logger("execution.terminal")


class TerminalRunner:
    """Run shell commands with timeout support and structured logging."""

    def __init__(self, timeout: int = 60, cwd: str | None = None) -> None:
        self.timeout = timeout
        self.cwd = cwd

    def run(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        """Execute a shell command and return a structured result.

        Args:
            command: The shell command to run (e.g. ``"npm run build"``).
            cwd: Working directory override for this call. Falls back to the
                instance-level ``cwd`` when not supplied.
            timeout: Timeout in seconds for this call. Falls back to the
                instance-level ``timeout`` when not supplied.

        Returns:
            A :class:`RunResult` with ``success``, ``stdout``, ``stderr``,
            ``command``, and ``returncode``.

        Note:
            ``shell=True`` is intentional — this runner executes
            developer-supplied commands in a controlled local environment.
        """
        effective_cwd = cwd if cwd is not None else self.cwd
        effective_timeout = timeout if timeout is not None else self.timeout

        log.info(
            "running command",
            command=command,
            cwd=effective_cwd,
            timeout=effective_timeout,
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=effective_cwd,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            log.warning(
                "command timed out",
                command=command,
                timeout=effective_timeout,
            )
            return RunResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {effective_timeout}s",
            )
        except Exception as exc:  # noqa: BLE001
            log.error("command failed to start", command=command, error=str(exc))
            return RunResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Failed to execute command: {exc}",
            )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        log.info(
            "command finished",
            command=command,
            returncode=result.returncode,
            success=result.returncode == 0,
        )
        log.debug(
            "command output",
            stdout=stdout[:_LOG_TRUNCATE],
            stderr=stderr[:_LOG_TRUNCATE],
        )

        return RunResult(
            command=command,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )


def run_command(
    command: str,
    *,
    timeout: int = 60,
    cwd: str | None = None,
) -> RunResult:
    """Run a shell command and return a structured result.

    Convenience wrapper around :class:`TerminalRunner`.

    Args:
        command: The shell command to run (e.g. ``"npm run build"``).
        timeout: Maximum seconds to wait before aborting. Defaults to 60.
        cwd: Working directory in which to run the command.

    Returns:
        A :class:`RunResult` with ``success``, ``stdout``, ``stderr``,
        ``command``, and ``returncode``.

    Example::

        result = run_command("npm run build")
        if result.success:
            print(result.stdout)
        else:
            print(result.stderr)
    """
    return TerminalRunner(timeout=timeout, cwd=cwd).run(command)
