"""
assignments/services/code_grader.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AI-проверка кода студента через GigaChat.

Отличие от ai_grader.py:
  - Контекст берётся из lesson.content (материал урока), а не из reference_answer.
  - Промпт заточен на анализ кода: архитектура, логика, соответствие материалу.
  - Вход: CodeSubmission (содержит code_content + output после выполнения).

Формат ответа GigaChat идентичен ai_grader — валидный JSON:
    {"score": <int 0–max_score>, "feedback": "<текст на русском>"}
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_gigachat.chat_models import GigaChat

if TYPE_CHECKING:
    from assignments.models import CodeSubmission

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = 'GigaChat-Pro'

# ---------------------------------------------------------------------------
# Промпты
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
ТЫ — АПИ-ИНТЕРФЕЙС ДЛЯ ОЦЕНКИ КОДА. ТЕБЕ ЗАПРЕЩЕНО ПИСАТЬ ОБЫЧНЫЙ ТЕКСТ.

ТВОЙ ЕДИНСТВЕННЫЙ ДОПУСТИМЫЙ ОТВЕТ — СТРОГО ВАЛИДНЫЙ JSON БЕЗ КАКИХ-ЛИБО ОБЁРТОК:
{{"score": <целое число от 0 до {max_score}>, "feedback": "<разбор на русском>"}}

АБСОЛЮТНЫЕ ЗАПРЕТЫ — НАРУШЕНИЕ НЕДОПУСТИМО:
- ЗАПРЕЩЕНО использовать ```json, ```, или любую другую markdown-разметку
- ЗАПРЕЩЕНО писать любой текст до открывающей {{ или после закрывающей }}
- ЗАПРЕЩЕНО добавлять приветствия, пояснения, предисловия, итоги
- ЗАПРЕЩЕНО переносить строку внутри JSON кроме как внутри значения "feedback"
- КРИТИЧЕСКИ ВАЖНО: ЗАПРЕЩЕНО использовать двойные кавычки (") внутри текста поля "feedback". Заменяй их на одинарные кавычки (') или угловые кавычки («»).

ТРЕБОВАНИЯ К ПОЛЯМ:
- "score": целое число, не строка, не дробь — только integer в диапазоне 0..{max_score}
- "feedback": одна строка на русском; содержит: что верно, что нарушает условие, рекомендации

ПРИМЕР ЕДИНСТВЕННО ДОПУСТИМОГО ФОРМАТА ОТВЕТА:
{{"score": 7, "feedback": "Студент верно применил цикл. Функция не обрабатывает пустой список — это разобрано в материале урока. Рекомендуется добавить проверку на входе."}}
"""

_HUMAN_TEMPLATE = """\
ЗАДАНИЕ: {assignment_title}

УСЛОВИЕ ЗАДАНИЯ:
{description}

МАТЕРИАЛ УРОКА (для сравнения):
{lesson_content}

КОД СТУДЕНТА (Python):
```python
{code_content}
```

РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ:
{execution_output}

Оцени код от 0 до {max_score} и верни только JSON.\
"""

# ---------------------------------------------------------------------------
# Dataclass результата
# ---------------------------------------------------------------------------

@dataclass
class CodeGradingResult:
    score: int
    feedback: str
    model_name: str


class CodeGradingError(Exception):
    """Сетевая / API-ошибка GigaChat при проверке кода."""


# ---------------------------------------------------------------------------
# Внутренние функции
# ---------------------------------------------------------------------------

def _parse_llm_response(text: str) -> dict | None:
    """
    Two-plan parser for GigaChat JSON responses.

    Plan A: strip markdown fences, locate outermost {...}, json.loads().
    Plan B (on JSONDecodeError): regex extraction of score and feedback fields.
    Returns None only when both plans fail.
    """
    # Strip ```json ... ``` and bare ``` fences
    cleaned = re.sub(r'```(?:json)?\s*', '', text, flags=re.IGNORECASE).strip()

    # Plan A — standard JSON parse
    start = cleaned.find('{')
    end   = cleaned.rfind('}')
    if start != -1 and end != -1 and start < end:
        candidate = cleaned[start:end + 1]
        try:
            parsed = json.loads(candidate)
            if 'score' in parsed and 'feedback' in parsed:
                return parsed
        except json.JSONDecodeError:
            pass  # fall through to Plan B

    # Plan B — regex extraction when JSON is malformed (unescaped or single quotes)
    score_m = re.search(r'["\']score["\']\s*:\s*(\d+)', cleaned)
    feedback_m = re.search(r'["\']feedback["\']\s*:\s*["\']+(.*)', cleaned, re.DOTALL)
    if score_m and feedback_m:
        feedback = re.sub(r'[\'"\s}]+$', '', feedback_m.group(1))
        return {'score': int(score_m.group(1)), 'feedback': feedback}

    return None


def _call_gigachat(
    assignment_title: str,
    description: str,
    lesson_content: str,
    code_content: str,
    execution_output: str,
    max_score: int,
) -> dict:
    model_name: str = getattr(settings, 'GIGACHAT_GRADER_MODEL', _DEFAULT_MODEL)

    llm = GigaChat(
        credentials=settings.GIGACHAT_AUTHORIZATION_KEY,
        model=model_name,
        temperature=0.1,
        verify_ssl_certs=False,
    )

    system_text = _SYSTEM_INSTRUCTION.format(max_score=max_score)
    human_text = _HUMAN_TEMPLATE.format(
        assignment_title=assignment_title,
        description=description,
        lesson_content=lesson_content[:3_000],   # не перегружаем контекстное окно
        code_content=code_content[:2_000],
        execution_output=execution_output[:1_000],
        max_score=max_score,
    )

    messages = [SystemMessage(content=system_text), HumanMessage(content=human_text)]

    logger.debug(
        'Code grading request → model=%s | assignment=%r | code_len=%d',
        model_name, assignment_title, len(code_content),
    )

    response = llm.invoke(messages)
    raw_text: str = (response.content or '').strip()

    # Temporary debug print — visible in Docker logs regardless of log level.
    # Remove once GigaChat response format is confirmed stable.
    print(f"[code_grader] RAW GIGACHAT RESPONSE: {raw_text!r}", flush=True)
    logger.warning('RAW GIGACHAT RESPONSE (code): %s', raw_text)

    parsed = _parse_llm_response(raw_text)
    if parsed is None:
        logger.warning('Could not parse GigaChat response: %.300s', raw_text)
        return _fallback(model_name, 'Модель не вернула JSON. Проверьте вручную.')

    try:
        score = max(0, min(max_score, int(parsed['score'])))
    except (TypeError, ValueError):
        score = 0

    return {
        'score':      score,
        'feedback':   str(parsed['feedback']),
        'model_name': model_name,
    }


def _fallback(model_name: str, reason: str) -> dict:
    return {'score': 0, 'feedback': reason, 'model_name': model_name}


# ---------------------------------------------------------------------------
# Публичный интерфейс
# ---------------------------------------------------------------------------

def grade_code_submission(submission: 'CodeSubmission') -> CodeGradingResult:
    """
    Оценивает попытку кода через GigaChat, используя материал урока как контекст.

    Обновляет submission.ai_feedback и submission.score в БД.
    Выбрасывает CodeGradingError при сетевой / API-ошибке.
    """
    a = submission.assignment
    lesson_content = a.lesson.content if a.lesson_id else ''

    try:
        raw = _call_gigachat(
            assignment_title=a.title,
            description=a.description,
            lesson_content=lesson_content,
            code_content=submission.code_content,
            execution_output=submission.output,
            max_score=a.max_score,
        )
    except Exception as exc:
        logger.exception(
            'GigaChat API error for code_submission pk=%d', submission.pk
        )
        raise CodeGradingError(f'GigaChat недоступен: {exc}') from exc

    result = CodeGradingResult(
        score=raw['score'],
        feedback=raw['feedback'],
        model_name=raw['model_name'],
    )

    submission.ai_feedback = result.feedback
    submission.score = result.score
    submission.save(update_fields=['ai_feedback', 'score'])

    logger.info(
        'Code grading done: submission pk=%d → score=%d/%d',
        submission.pk, result.score, a.max_score,
    )
    return result
