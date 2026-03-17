from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class RunResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


class ExecutionRunner:
    def run(self, command: str, cwd: str | None = None) -> RunResult:
        """Run a shell command and return a structured result.

        Note: shell=True is intentional — this runner executes developer-supplied
        commands in a controlled local environment.
        """
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return RunResult(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
