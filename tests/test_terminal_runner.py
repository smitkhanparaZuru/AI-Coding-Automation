from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from aica.execution.terminal import TerminalRunner, run_command


class TestRunCommand:
    def test_successful_command(self):
        result = run_command("echo hello")
        assert result.success is True
        assert "hello" in result.stdout
        assert result.returncode == 0
        assert result.command == "echo hello"

    def test_failing_command(self):
        result = run_command("exit 1", timeout=10)
        assert result.success is False
        assert result.returncode != 0

    def test_stderr_captured(self):
        # Write to stderr via shell redirection
        result = run_command("echo errtext 1>&2", timeout=10)
        assert result.success is True
        assert "errtext" in result.stderr

    def test_timeout_returns_failure(self):
        exc = subprocess.TimeoutExpired(cmd="sleep 999", timeout=1)
        with patch("subprocess.run", side_effect=exc):
            result = run_command("sleep 999", timeout=1)
        assert result.success is False
        assert result.returncode == -1
        assert "timed out" in result.stderr.lower()
        assert "1s" in result.stderr

    def test_os_error_returns_failure(self):
        with patch("subprocess.run", side_effect=OSError("No such file")):
            result = run_command("nonexistent_cmd_xyz")
        assert result.success is False
        assert result.returncode == -1
        assert "No such file" in result.stderr

    def test_stdout_stripped(self):
        result = run_command("echo   hello   ")
        assert result.stdout == result.stdout.strip()


class TestTerminalRunner:
    def test_run_with_explicit_cwd(self, tmp_path):
        runner = TerminalRunner()
        result = runner.run("echo cwd_test", cwd=str(tmp_path))
        assert result.success is True
        assert "cwd_test" in result.stdout

    def test_instance_timeout_used_as_default(self):
        exc = subprocess.TimeoutExpired(cmd="sleep 999", timeout=5)
        runner = TerminalRunner(timeout=5)
        with patch("subprocess.run", side_effect=exc):
            result = runner.run("sleep 999")
        assert result.success is False
        assert "5s" in result.stderr

    def test_per_call_timeout_overrides_instance(self):
        exc = subprocess.TimeoutExpired(cmd="sleep 999", timeout=3)
        runner = TerminalRunner(timeout=99)
        with patch("subprocess.run", side_effect=exc):
            result = runner.run("sleep 999", timeout=3)
        assert result.success is False
        assert "3s" in result.stderr

    def test_per_call_cwd_overrides_instance(self, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        runner = TerminalRunner(cwd=str(tmp_path))
        result = runner.run("echo hi", cwd=str(other))
        assert result.success is True

    def test_instance_cwd_used_when_not_overridden(self, tmp_path):
        runner = TerminalRunner(cwd=str(tmp_path))
        result = runner.run("echo hi")
        assert result.success is True
