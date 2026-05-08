"""
assignments/services/ai_grader.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Сервисный слой для автоматической оценки ответов студентов через GigaChat.

Архитектура промпта:
    SystemMessage  — роль ИИ-преподавателя и строгие правила формата вывода.
    HumanMessage   — конкретные данные задания: условие, эталон, ответ студента.

Разделение System/Human важно для chat-моделей: GigaChat следует ролевым
инструкциям из SystemMessage строже, чем из единого текста.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_gigachat.chat_models import GigaChat

if TYPE_CHECKING:
    from assignments.models import AIEvaluation, AssignmentSubmission

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Константы модели
# ---------------------------------------------------------------------------

# GigaChat-Pro точнее следует инструкциям и лучше форматирует JSON.
# При недоступности Pro — Django-настройка GIGACHAT_GRADER_MODEL позволяет
# переключиться на базовый "GigaChat" без правки кода.
_DEFAULT_MODEL = "GigaChat-Pro"


# ---------------------------------------------------------------------------
# Промпт: системная инструкция (роль + формат)
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
Ты — строгий и объективный ИИ-преподаватель. Твоя задача — оценить письменный \
ответ студента на учебное задание.

ПРАВИЛА, которые ты обязан соблюдать НЕУКОСНИТЕЛЬНО:
1. Отвечай ТОЛЬКО валидным JSON-объектом. Никакого текста до или после него.
2. JSON должен содержать ровно два ключа:
   - "score"    — целое число от 0 до {max_score} включительно.
   - "feedback" — строка с развёрнутым разбором на русском языке.
3. В "feedback" обязательно укажи:
   а) Что студент сделал правильно.
   б) Какие ключевые моменты упущены или изложены неверно.
   в) Конкретные рекомендации по улучшению.
4. Будь справедлив: полный и точный ответ заслуживает высокого балла.
5. Не придумывай информацию вне эталонного ответа.

Пример единственно допустимого формата ответа:
{{"score": 78, "feedback": "Студент верно определил ключевое понятие и привёл \
два релевантных примера. Однако упущен третий критерий из условия задания — \
сравнение с альтернативными подходами. Рекомендуется дополнить ответ анализом \
компромиссов."}}
"""

# ---------------------------------------------------------------------------
# Промпт: пользовательское сообщение (динамические данные задания)
# ---------------------------------------------------------------------------

_HUMAN_MESSAGE_TEMPLATE = """\
ЗАДАНИЕ: {assignment_title}

УСЛОВИЕ ЗАДАНИЯ:
{assignment_description}

ЭТАЛОННЫЙ ОТВЕТ / КРИТЕРИИ ОЦЕНКИ:
{reference_answer}

ОТВЕТ СТУДЕНТА:
{student_answer}

Оцени ответ студента по шкале от 0 до {max_score}. \
Верни только JSON в формате, указанном в инструкции.\
"""


# ---------------------------------------------------------------------------
# Dataclass — структурированный внутренний результат
# ---------------------------------------------------------------------------

@dataclass
class GradingResult:
    score: int
    feedback: str
    model_name: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


# ---------------------------------------------------------------------------
# Вспомогательная функция: извлечение токенов из ответа LangChain
# ---------------------------------------------------------------------------

def _extract_token_usage(response) -> tuple[int | None, int | None]:
    """
    Пробует получить количество токенов из объекта AIMessage.

    LangChain предоставляет два места с данными о токенах:
      1. response.usage_metadata  — стандарт LangChain ≥ 0.2
         {'input_tokens': N, 'output_tokens': M, 'total_tokens': K}
      2. response.response_metadata['token_usage']  — провайдерский формат
         {'prompt_tokens': N, 'completion_tokens': M, 'total_tokens': K}

    Возвращает (prompt_tokens, completion_tokens) или (None, None).
    """
    # Вариант 1: стандартный usage_metadata (предпочтительный)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return (
            usage.get("input_tokens"),
            usage.get("output_tokens"),
        )

    # Вариант 2: response_metadata от провайдера
    meta = getattr(response, "response_metadata", {}) or {}
    token_usage = meta.get("token_usage", {})
    if token_usage:
        return (
            token_usage.get("prompt_tokens"),
            token_usage.get("completion_tokens"),
        )

    return None, None


# ---------------------------------------------------------------------------
# Реальный вызов GigaChat
# ---------------------------------------------------------------------------

def _call_llm_real(
    assignment_title: str,
    assignment_description: str,
    reference_answer: str,
    student_answer: str,
    max_score: int,
) -> dict:
    """
    Отправляет задание и ответ студента в GigaChat, возвращает разобранный dict.

    Использует двухсообщенческую схему (System + Human), которая
    обеспечивает более строгое следование инструкциям формата.

    Возвращаемый dict гарантированно содержит ключи:
        "score"             — int, зажатый в [0, max_score]
        "feedback"          — str
        "model_name"        — str
        "prompt_tokens"     — int | None
        "completion_tokens" — int | None

    При любой ошибке парсинга JSON возвращает фоллбэк-словарь
    (score=0, feedback=<сообщение об ошибке>) — НЕ выбрасывает исключение.
    Сетевые ошибки GigaChat пропускаются выше и обрабатываются в grade_submission.
    """
    model_name: str = getattr(settings, "GIGACHAT_GRADER_MODEL", _DEFAULT_MODEL)

    llm = GigaChat(
        credentials=settings.GIGACHAT_AUTHORIZATION_KEY,
        model=model_name,
        temperature=0.1,        # минимальная случайность → стабильный JSON
        verify_ssl_certs=False,  # самоподписанный сертификат Сбера
    )

    system_text = _SYSTEM_INSTRUCTION.format(max_score=max_score)
    human_text = _HUMAN_MESSAGE_TEMPLATE.format(
        assignment_title=assignment_title,
        assignment_description=assignment_description,
        reference_answer=reference_answer,
        student_answer=student_answer,
        max_score=max_score,
    )

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=human_text),
    ]

    logger.debug(
        "Sending grading request to %s | max_score=%d | "
        "reference_len=%d | student_len=%d",
        model_name,
        max_score,
        len(reference_answer),
        len(student_answer),
    )

    response = llm.invoke(messages)
    raw_text: str = (response.content or "").strip()

    logger.debug("Raw LLM response (first 300 chars): %.300s", raw_text)

    # --- Парсинг JSON ---
    # GigaChat иногда оборачивает JSON в markdown-блок ```json ... ```
    # Ищем первый {...} в тексте, игнорируя обёртку.
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)

    if not json_match:
        logger.warning(
            "GigaChat did not return a JSON object. Raw response: %.300s", raw_text
        )
        return _fallback_result(
            model_name=model_name,
            reason="Модель не вернула JSON. Задание передано на ручную проверку.",
        )

    try:
        parsed: dict = json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse error: %s. Matched text: %.200s", exc, json_match.group()
        )
        return _fallback_result(
            model_name=model_name,
            reason=f"Ошибка разбора ответа ИИ ({exc}). Задание передано на ручную проверку.",
        )

    # --- Валидация обязательных полей ---
    if "score" not in parsed or "feedback" not in parsed:
        logger.warning(
            "LLM response missing required keys. Keys found: %s", list(parsed.keys())
        )
        return _fallback_result(
            model_name=model_name,
            reason="Ответ ИИ не содержит обязательных полей. Задание передано на ручную проверку.",
        )

    # Зажимаем балл в допустимый диапазон (модель иногда выходит за границы)
    try:
        score = max(0, min(max_score, int(parsed["score"])))
    except (TypeError, ValueError):
        logger.warning("Invalid score value from LLM: %r", parsed.get("score"))
        score = 0

    prompt_tokens, completion_tokens = _extract_token_usage(response)

    return {
        "score":             score,
        "feedback":          str(parsed["feedback"]),
        "model_name":        model_name,
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def _fallback_result(model_name: str, reason: str) -> dict:
    """Возвращает безопасный фоллбэк при невозможности распарсить ответ LLM."""
    return {
        "score":             0,
        "feedback":          reason,
        "model_name":        model_name,
        "prompt_tokens":     None,
        "completion_tokens": None,
    }


# ---------------------------------------------------------------------------
# Публичный интерфейс
# ---------------------------------------------------------------------------

def build_grading_prompt(submission: "AssignmentSubmission") -> str:
    """
    Возвращает текст HumanMessage для логирования и отладки.

    В самом grade_submission данные передаются отдельными аргументами
    в _call_llm_real — это позволяет сформировать SystemMessage + HumanMessage
    как отдельные объекты. Функция сохранена для обратной совместимости
    и использования в тестах.
    """
    a = submission.assignment
    return _HUMAN_MESSAGE_TEMPLATE.format(
        assignment_title=a.title,
        assignment_description=a.description,
        reference_answer=a.reference_answer,
        student_answer=submission.answer_text,
        max_score=a.max_score,
    )


def grade_submission(submission: "AssignmentSubmission") -> "AIEvaluation":
    """
    Основная точка входа: оценивает ответ студента через GigaChat и сохраняет результат.

    Жизненный цикл:
        1. Извлекает данные задания и ответ студента.
        2. Передаёт в _call_llm_real — реальный вызов GigaChat.
        3. Сохраняет AIEvaluation и обновляет submission.status → AI_CHECKED
           в одной транзакции.

    Выбрасывает GradingError при сетевой/API-ошибке GigaChat.
    Ошибки парсинга JSON не выбрасывают исключений — возвращается фоллбэк
    с score=0 и пояснительным feedback.
    """
    from assignments.models import AIEvaluation, AssignmentSubmission

    a = submission.assignment

    logger.info(
        "Starting grading: submission pk=%d | assignment=%r | student=%r",
        submission.pk,
        a.title,
        submission.student.username,
    )

    try:
        raw: dict = _call_llm_real(
            assignment_title=a.title,
            assignment_description=a.description,
            reference_answer=a.reference_answer,
            student_answer=submission.answer_text,
            max_score=a.max_score,
        )
    except Exception as exc:
        # Сетевая ошибка, таймаут, недоступность API — прерываем проверку.
        # Submission остаётся в статусе PENDING, преподаватель может
        # запустить повторную проверку через /submissions/{id}/regrade/
        logger.exception(
            "GigaChat API call failed for submission pk=%d", submission.pk
        )
        raise GradingError(f"GigaChat недоступен: {exc}") from exc

    result = GradingResult(
        score=raw["score"],
        feedback=raw["feedback"],
        model_name=raw["model_name"],
        prompt_tokens=raw["prompt_tokens"],
        completion_tokens=raw["completion_tokens"],
    )

    with transaction.atomic():
        # При повторной проверке (regrade) — удаляем старую оценку
        AIEvaluation.objects.filter(submission=submission).delete()

        evaluation = AIEvaluation.objects.create(
            submission=submission,
            score=result.score,
            feedback=result.feedback,
            model_name=result.model_name,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )

        submission.status = AssignmentSubmission.Status.AI_CHECKED
        submission.save(update_fields=["status"])

    logger.info(
        "Grading complete: submission pk=%d → score=%d/%d | tokens: in=%s out=%s",
        submission.pk,
        result.score,
        a.max_score,
        result.prompt_tokens,
        result.completion_tokens,
    )
    return evaluation


# ---------------------------------------------------------------------------
# Исключения
# ---------------------------------------------------------------------------

class GradingError(Exception):
    """
    Выбрасывается при сетевой или API-ошибке GigaChat.
    Ошибки парсинга JSON сюда не попадают — они обрабатываются фоллбэком.
    """
