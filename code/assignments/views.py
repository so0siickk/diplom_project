from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from courses.models import Assignment as CourseAssignment

from .models import AssignmentSubmission, CodeSubmission, EssaySubmission, OpenAssignment
from .permissions import (
    IsAssignmentAuthorOrReadOnly,
    IsSubmissionOwnerOrTeacher,
    IsTeacher,
    IsTeacherOrReadOnly,
)
from .serializers import (
    CodeSubmissionSerializer,
    CodeSubmitSerializer,
    EssaySubmissionSerializer,
    EssaySubmitSerializer,
    OpenAssignmentDetailTeacherSerializer,
    OpenAssignmentSerializer,
    OpenAssignmentWriteSerializer,
    SubmissionApproveSerializer,
    SubmissionCreateSerializer,
    SubmissionReviewSerializer,
    SubmissionStudentSerializer,
)
from .services.ai_grader import GradingError, grade_submission
from .services.code_grader import CodeGradingError, grade_code_submission
from .services.code_runner import run_python_code
from .services.essay_grader import EssayGradingError, grade_essay_submission

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAssignment ViewSet
# ---------------------------------------------------------------------------

@extend_schema(tags=["Assignments"])
class OpenAssignmentViewSet(viewsets.ModelViewSet):
    """
    CRUD заданий с открытым ответом.

    - Преподаватели: полный доступ к своим заданиям (включая reference_answer).
    - Студенты: только чтение (reference_answer скрыт).

    Дополнительные actions:
        POST /{id}/submit/          — студент отправляет ответ
        GET  /{id}/submissions/     — преподаватель смотрит все ответы
        GET  /{id}/my-submission/   — студент смотрит свой ответ
    """

    permission_classes = [IsAuthenticated, IsTeacherOrReadOnly, IsAssignmentAuthorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = OpenAssignment.objects.select_related("created_by", "lesson__module__course")
        if user.is_staff or user.role == "teacher":
            # Преподаватель видит только свои задания
            return qs if user.is_staff else qs.filter(created_by=user)
        # Студент видит только активные задания
        return qs.filter(is_active=True)

    def get_serializer_class(self):
        user = self.request.user
        if self.request.method in ("POST", "PUT", "PATCH"):
            return OpenAssignmentWriteSerializer
        # Преподаватель получает полный сериализатор с reference_answer
        if user.is_authenticated and (user.role == "teacher" or user.is_staff):
            return OpenAssignmentDetailTeacherSerializer
        return OpenAssignmentSerializer

    def perform_create(self, serializer) -> None:
        serializer.save(created_by=self.request.user)

    # ------------------------------------------------------------------
    # Action: студент отправляет ответ → запускает AI-проверку
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Студент отправляет ответ на задание",
        request=SubmissionCreateSerializer,
        responses={
            201: SubmissionStudentSerializer,
            400: OpenApiResponse(description="Невалидные данные или ответ уже отправлен"),
            403: OpenApiResponse(description="Задание неактивно"),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="submit",
        permission_classes=[IsAuthenticated],
    )
    def submit(self, request, pk=None) -> Response:
        """
        POST /api/v1/assignments/{id}/submit/

        1. Создаёт AssignmentSubmission.
        2. Синхронно вызывает AI-грейдер (в production замените на Celery-задачу).
        3. Возвращает статус ответа вместе с AI-оценкой.
        """
        assignment: OpenAssignment = self.get_object()

        if not assignment.is_active:
            return Response(
                {"detail": "Задание неактивно и не принимает ответы."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Проверяем повторную отправку
        if AssignmentSubmission.objects.filter(
            assignment=assignment, student=request.user
        ).exists():
            return Response(
                {"detail": "Вы уже отправили ответ на это задание."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=request.user,
            answer_text=serializer.validated_data["answer_text"],
        )

        # Запуск AI-грейдера (синхронно; TODO: вынести в Celery при высокой нагрузке)
        try:
            grade_submission(submission)
        except GradingError as exc:
            logger.warning(
                "AI grading failed for submission pk=%d: %s", submission.pk, exc
            )
            # Ответ уже сохранён со статусом PENDING — не блокируем студента

        # Обновляем объект из БД, чтобы получить актуальный статус и оценку
        submission.refresh_from_db()
        return Response(
            SubmissionStudentSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Action: преподаватель получает список ответов с AI-оценкой
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Список ответов на задание (только для преподавателя)",
        responses={200: SubmissionReviewSerializer(many=True)},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="submissions",
        permission_classes=[IsAuthenticated, IsTeacher],
    )
    def submissions(self, request, pk=None) -> Response:
        """
        GET /api/v1/assignments/{id}/submissions/

        Возвращает все ответы на задание, включая AI-оценку.
        Доступно только преподавателю — автору задания.
        """
        assignment: OpenAssignment = self.get_object()

        # Дополнительная проверка: только автор задания (не любой преподаватель)
        if assignment.created_by_id != request.user.pk and not request.user.is_staff:
            return Response(
                {"detail": "У вас нет доступа к ответам этого задания."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = (
            AssignmentSubmission.objects
            .filter(assignment=assignment)
            .select_related("student", "ai_evaluation")
            .order_by("-submitted_at")
        )
        serializer = SubmissionReviewSerializer(qs, many=True)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Action: студент смотрит свой ответ и AI-фидбек
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Ответ текущего студента на задание",
        responses={
            200: SubmissionStudentSerializer,
            404: OpenApiResponse(description="Ответ ещё не отправлен"),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="my-submission",
        permission_classes=[IsAuthenticated],
    )
    def my_submission(self, request, pk=None) -> Response:
        """
        GET /api/v1/assignments/{id}/my-submission/

        Возвращает собственный ответ студента (если уже отправлен).
        """
        assignment: OpenAssignment = self.get_object()
        try:
            submission = (
                AssignmentSubmission.objects
                .select_related("ai_evaluation")
                .get(assignment=assignment, student=request.user)
            )
        except AssignmentSubmission.DoesNotExist:
            return Response(
                {"detail": "Вы ещё не отправили ответ на это задание."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SubmissionStudentSerializer(submission).data)


# ---------------------------------------------------------------------------
# Submission ViewSet — утверждение итогового балла
# ---------------------------------------------------------------------------

@extend_schema(tags=["Assignments"])
class SubmissionViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Операции над конкретным ответом студента.

    Основное применение — эндпоинт approve для преподавателя.
    Список доступен преподавателю (все ответы на его задания)
    и студенту (только свои ответы).
    """

    permission_classes = [IsAuthenticated, IsSubmissionOwnerOrTeacher]

    def get_queryset(self):
        user = self.request.user
        qs = AssignmentSubmission.objects.select_related(
            "assignment__created_by", "student", "ai_evaluation"
        )
        if user.is_staff:
            return qs
        if user.role == "teacher":
            return qs.filter(assignment__created_by=user)
        # Студент видит только свои ответы
        return qs.filter(student=user)

    def get_serializer_class(self):
        if self.action == "approve":
            return SubmissionApproveSerializer
        user = self.request.user
        if user.is_authenticated and (user.role == "teacher" or user.is_staff):
            return SubmissionReviewSerializer
        return SubmissionStudentSerializer

    # ------------------------------------------------------------------
    # Action: преподаватель утверждает или переопределяет балл
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Утвердить итоговый балл (преподаватель)",
        request=SubmissionApproveSerializer,
        responses={
            200: SubmissionReviewSerializer,
            403: OpenApiResponse(description="Только преподаватель-автор задания"),
        },
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="approve",
        permission_classes=[IsAuthenticated, IsTeacher],
    )
    def approve(self, request, pk=None) -> Response:
        """
        PATCH /api/v1/submissions/{id}/approve/
        { "final_score": 85, "teacher_comment": "Хорошая работа, но..." }

        Преподаватель соглашается с оценкой AI или задаёт свой балл.
        Переводит статус в APPROVED.
        """
        submission: AssignmentSubmission = self.get_object()

        # Только автор задания может утвердить балл
        if (
            submission.assignment.created_by_id != request.user.pk
            and not request.user.is_staff
        ):
            return Response(
                {"detail": "Вы не являетесь автором этого задания."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SubmissionApproveSerializer(
            submission, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        return Response(SubmissionReviewSerializer(updated).data)

    # ------------------------------------------------------------------
    # Action: повторный запуск AI-грейдера (например, после правок задания)
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Повторно запустить AI-проверку (преподаватель)",
        responses={
            200: SubmissionStudentSerializer,
            503: OpenApiResponse(description="LLM недоступна"),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="regrade",
        permission_classes=[IsAuthenticated, IsTeacher],
    )
    def regrade(self, request, pk=None) -> Response:
        """
        POST /api/v1/submissions/{id}/regrade/

        Преподаватель может запустить повторную AI-оценку, например,
        после редактирования эталонного ответа.
        """
        submission: AssignmentSubmission = self.get_object()

        if submission.assignment.created_by_id != request.user.pk and not request.user.is_staff:
            return Response(
                {"detail": "Вы не являетесь автором этого задания."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            grade_submission(submission)
        except GradingError as exc:
            return Response(
                {"detail": f"AI-грейдер недоступен: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        submission.refresh_from_db()
        return Response(SubmissionStudentSerializer(submission).data)


# ---------------------------------------------------------------------------
# CodeAssignmentViewSet — приём и проверка кода
# ---------------------------------------------------------------------------

@extend_schema(tags=["Code Assignments"])
class CodeAssignmentViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Работа с заданиями типа «code» и приём кода от студентов.

    Эндпоинты:
        GET  /api/v1/code-assignments/           — список доступных заданий типа code
        GET  /api/v1/code-assignments/{id}/      — детали задания
        POST /api/v1/code-assignments/{id}/submit/ — студент отправляет код
        GET  /api/v1/code-assignments/{id}/my-submissions/ — история попыток студента
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CodeSubmissionSerializer  # по умолчанию для list/retrieve

    def get_queryset(self):
        return (
            CourseAssignment.objects
            .filter(assignment_type=CourseAssignment.Type.CODE)
            .select_related('lesson__module__course')
        )

    # ------------------------------------------------------------------
    # Action: студент отправляет код → выполнение → AI-оценка
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Отправить код на выполнение и AI-проверку",
        request=CodeSubmitSerializer,
        responses={
            201: CodeSubmissionSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            422: OpenApiResponse(description="Задание не является заданием типа code"),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="submit",
        permission_classes=[IsAuthenticated],
    )
    def submit(self, request, pk=None) -> Response:
        """
        POST /api/v1/code-assignments/{id}/submit/

        Пайплайн:
            1. Валидируем входные данные (code_content).
            2. Сохраняем CodeSubmission со статусом PENDING.
            3. Выполняем код в subprocess (с таймаутом 5 с).
            4. Обновляем статус (SUCCESS / FAILED) и output.
            5. Запускаем AI-грейдер → пишем ai_feedback и score.
            6. Возвращаем полный сериализованный объект попытки.

        Множественные попытки разрешены — студент может итерировать код.
        AI-оценка выставляется синхронно; при недоступности GigaChat
        submission сохраняется без score и ai_feedback (не блокируем ответ).
        """
        assignment = self.get_object()

        # Защита от случайного вызова на не-code задании (дополнительный guard)
        if assignment.assignment_type != CourseAssignment.Type.CODE:
            return Response(
                {"detail": "Этот эндпоинт только для заданий типа 'code'."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if assignment.max_attempts > 0:
            attempt_count = CodeSubmission.objects.filter(
                assignment=assignment, student=request.user
            ).count()
            if attempt_count >= assignment.max_attempts:
                return Response(
                    {"detail": "Лимит попыток исчерпан"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = CodeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code_content: str = serializer.validated_data["code_content"]

        # 1. Сохраняем попытку в статусе PENDING
        submission = CodeSubmission.objects.create(
            student=request.user,
            assignment=assignment,
            code_content=code_content,
            status=CodeSubmission.Status.PENDING,
        )

        # 2. Выполняем код в subprocess
        execution = run_python_code(code_content)

        submission.output = execution.output
        submission.status = (
            CodeSubmission.Status.SUCCESS
            if execution.success
            else CodeSubmission.Status.FAILED
        )
        submission.save(update_fields=["output", "status"])

        logger.info(
            "Code executed: submission uuid=%s | success=%s | output_len=%d",
            submission.uuid,
            execution.success,
            len(execution.output),
        )

        # 3. AI-грейдинг (даже если код упал — анализируем логику)
        try:
            grade_code_submission(submission)
        except CodeGradingError as exc:
            logger.warning(
                "AI code grading failed for submission uuid=%s: %s",
                submission.uuid,
                exc,
            )
            # Возвращаем попытку без оценки — студент видит вывод выполнения

        submission.refresh_from_db()
        return Response(
            CodeSubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Action: история попыток текущего студента
    # ------------------------------------------------------------------

    @extend_schema(
        summary="История попыток текущего студента на это задание",
        responses={200: CodeSubmissionSerializer(many=True)},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="my-submissions",
        permission_classes=[IsAuthenticated],
    )
    def my_submissions(self, request, pk=None) -> Response:
        """
        GET /api/v1/code-assignments/{id}/my-submissions/

        Возвращает все попытки текущего студента по этому заданию,
        отсортированные от новой к старой.
        """
        assignment = self.get_object()
        qs = (
            CodeSubmission.objects
            .filter(assignment=assignment, student=request.user)
            .order_by('-submitted_at')
        )
        return Response(CodeSubmissionSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# EssayAssignmentViewSet — приём и AI-проверка эссе
# ---------------------------------------------------------------------------

@extend_schema(tags=["Essay Assignments"])
class EssayAssignmentViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Работа с заданиями типа «essay» и приём письменных ответов студентов.

    Эндпоинты:
        GET  /api/v1/essay-assignments/                — список заданий типа essay
        GET  /api/v1/essay-assignments/{id}/           — детали задания
        POST /api/v1/essay-assignments/{id}/submit/    — студент отправляет ответ
        GET  /api/v1/essay-assignments/{id}/my-submissions/ — история попыток
    """

    permission_classes = [IsAuthenticated]
    serializer_class = EssaySubmissionSerializer

    def get_queryset(self):
        return (
            CourseAssignment.objects
            .filter(assignment_type=CourseAssignment.Type.ESSAY)
            .select_related('lesson__module__course')
        )

    # ------------------------------------------------------------------
    # Action: студент отправляет эссе → AI-проверка
    # ------------------------------------------------------------------

    @extend_schema(
        summary="Отправить письменный ответ на AI-проверку",
        request=EssaySubmitSerializer,
        responses={
            201: EssaySubmissionSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            422: OpenApiResponse(description="Задание не является заданием типа essay"),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="submit",
        permission_classes=[IsAuthenticated],
    )
    def submit(self, request, pk=None) -> Response:
        """
        POST /api/v1/essay-assignments/{id}/submit/

        Пайплайн:
            1. Валидируем текст ответа.
            2. Сохраняем EssaySubmission.
            3. Запускаем grade_essay_submission() — GigaChat сравнивает
               ответ с материалом урока и выставляет оценку.
            4. Возвращаем объект попытки с оценкой и фидбеком.

        Множественные попытки разрешены.
        При недоступности GigaChat submission сохраняется без оценки.
        """
        assignment = self.get_object()

        if assignment.assignment_type != CourseAssignment.Type.ESSAY:
            return Response(
                {"detail": "Этот эндпоинт только для заданий типа 'essay'."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if assignment.max_attempts > 0:
            attempt_count = EssaySubmission.objects.filter(
                assignment=assignment, student=request.user
            ).count()
            if attempt_count >= assignment.max_attempts:
                return Response(
                    {"detail": "Лимит попыток исчерпан"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = EssaySubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text_content: str = serializer.validated_data["text_content"]

        submission = EssaySubmission.objects.create(
            student=request.user,
            assignment=assignment,
            text_content=text_content,
        )

        try:
            grade_essay_submission(submission)
        except EssayGradingError as exc:
            logger.warning(
                "AI essay grading failed for submission pk=%d: %s",
                submission.pk, exc,
            )

        submission.refresh_from_db()
        return Response(
            EssaySubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Action: история попыток текущего студента
    # ------------------------------------------------------------------

    @extend_schema(
        summary="История попыток текущего студента на это задание",
        responses={200: EssaySubmissionSerializer(many=True)},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="my-submissions",
        permission_classes=[IsAuthenticated],
    )
    def my_submissions(self, request, pk=None) -> Response:
        """
        GET /api/v1/essay-assignments/{id}/my-submissions/
        """
        assignment = self.get_object()
        qs = (
            EssaySubmission.objects
            .filter(assignment=assignment, student=request.user)
            .order_by('-created_at')
        )
        return Response(EssaySubmissionSerializer(qs, many=True).data)
