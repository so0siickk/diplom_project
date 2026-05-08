"""
assignments/services/code_runner.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Запускает код студента в дочернем процессе (Python subprocess).

Ограничения:
  - Таймаут: 5 секунд (настраивается через CODE_RUNNER_TIMEOUT в settings).
  - Максимальный вывод: 4 000 символов (обрезается, чтобы не переполнять БД и промпт).
  - Запускается тот же интерпретатор, что и Django (sys.executable).

ВАЖНО: это демо-песочница. В production замените на Docker / nsjail / Firecracker.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from django.conf import settings

_TIMEOUT: int = getattr(settings, 'CODE_RUNNER_TIMEOUT', 5)
_MAX_OUTPUT: int = 4_000


@dataclass
class ExecutionResult:
    output: str   # stdout + stderr (усечённый)
    success: bool


def run_python_code(code: str, timeout: int = _TIMEOUT) -> ExecutionResult:
    """
    Выполняет Python-код в изолированном subprocess.

    Объединяет stdout и stderr, усекает до _MAX_OUTPUT символов,
    возвращает флаг успеха (returncode == 0).
    """
    try:
        proc = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        combined = (proc.stdout + proc.stderr).strip()
        return ExecutionResult(
            output=combined[:_MAX_OUTPUT],
            success=(proc.returncode == 0),
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            output=f'[TimeoutError] Execution exceeded {timeout}s limit.',
            success=False,
        )
    except Exception as exc:
        return ExecutionResult(
            output=f'[RunnerError] {exc}',
            success=False,
        )
