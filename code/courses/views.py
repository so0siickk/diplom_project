import logging
import os

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView

from .models import Course, CourseDocument, Lesson, LessonMaterial, Module, Enrollment, Quiz
from analytics.models import QuizAttempt, UserLessonProgress
from .serializers import (
    CourseSerializer, CourseWriteSerializer,
    ModuleSerializer, ModuleWriteSerializer,
    LessonSerializer, LessonWriteSerializer,
    CourseDocumentListSerializer,
    CourseDocumentUploadSerializer,
    CourseDocumentDetailSerializer,
    LessonMaterialSerializer,
    QuizSerializer,
)
from .permissions import IsOwnerOrReadOnly, IsEnrolledOrOwner
from .services.document_parser import (
    extract_text_from_file,
    UnsupportedFileTypeError,
    ParsingError,
)

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from analytics.models import UserLessonProgress
from assistant.vector_store import index_lesson_content

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ViewSets — full CRUD with owner-based write permissions
# ---------------------------------------------------------------------------

@extend_schema(tags=['Courses'])
class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return (
            Course.objects
            .select_related('owner')
            .prefetch_related('modules__lessons')
        )

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return CourseWriteSerializer
        return CourseSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(
        tags=['Courses'],
        summary='Enroll the current user in this course',
        responses={201: None, 200: None},
    )
    @action(detail=True, methods=['post'], url_path='enroll',
            permission_classes=[IsAuthenticated])
    def enroll(self, request, pk=None):
        # Используем get_object_or_404 напрямую, чтобы обойти object-level
        # проверку IsOwnerOrReadOnly (self.get_object() её триггерит).
        course = get_object_or_404(Course, pk=pk)
        _, created = Enrollment.objects.get_or_create(user=request.user, course=course)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({'enrolled': True, 'created': created}, status=code)

    # ------------------------------------------------------------------
    # Action: загрузка и парсинг документа (PDF / DOCX)
    # ------------------------------------------------------------------

    @extend_schema(
        tags=['Courses'],
        summary='Список загруженных документов курса',
        responses={200: CourseDocumentListSerializer(many=True)},
    )
    @extend_schema(
        tags=['Courses'],
        methods=['POST'],
        summary='Загрузить документ (PDF/DOCX) и извлечь текст',
        request={'multipart/form-data': CourseDocumentUploadSerializer},
        responses={
            201: CourseDocumentDetailSerializer,
            400: OpenApiResponse(description='Невалидный файл или неподдерживаемый формат'),
            403: OpenApiResponse(description='Только владелец курса'),
        },
    )
    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='documents',
        parser_classes=None,  # наследует парсеры проекта (включает MultiPartParser)
    )
    def documents(self, request, pk=None) -> Response:
        """
        GET  /api/v1/courses/{id}/documents/ — список документов курса.
        POST /api/v1/courses/{id}/documents/ — загрузка нового документа.

        POST принимает multipart/form-data с полем file (PDF или DOCX).
        После сохранения запускается синхронный парсинг текста.
        """
        course = self.get_object()

        if request.method == 'GET':
            return self._list_documents(course)

        # POST — только владелец курса
        if course.owner_id != request.user.pk and not request.user.is_staff:
            return Response(
                {'detail': 'Загружать документы может только владелец курса.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return self._upload_document(request, course)

    def _list_documents(self, course: Course) -> Response:
        """Возвращает список документов без поля extracted_text."""
        docs = (
            CourseDocument.objects
            .filter(course=course)
            .select_related('uploaded_by')
        )
        return Response(CourseDocumentListSerializer(docs, many=True).data)

    def _upload_document(self, request, course: Course) -> Response:
        """
        Сохраняет файл, запускает парсинг и обновляет статус документа.
        """
        upload_serializer = CourseDocumentUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        uploaded_file = upload_serializer.validated_data['file']
        _, ext = os.path.splitext(uploaded_file.name)

        # Создаём запись в БД со статусом PENDING
        document = CourseDocument.objects.create(
            course=course,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            uploaded_by=request.user,
            status=CourseDocument.Status.PENDING,
        )

        # Парсим текст из файла
        try:
            uploaded_file.seek(0)  # сбрасываем позицию после валидации
            extracted = extract_text_from_file(uploaded_file, ext)

            document.extracted_text = extracted
            document.status = CourseDocument.Status.PARSED
            document.save(update_fields=['extracted_text', 'status'])

            logger.info(
                "Document pk=%d parsed successfully: %d chars extracted",
                document.pk,
                len(extracted),
            )

            # Запускаем векторизацию в фоновом потоке — не блокируем ответ.
            # После завершения поток обновит статус документа до INDEXED (или ERROR).
            from assistant.services.vectorizer import index_document_async
            index_document_async(document)

        except (UnsupportedFileTypeError, ParsingError) as exc:
            document.status = CourseDocument.Status.ERROR
            document.error_message = str(exc)
            document.save(update_fields=['status', 'error_message'])
            logger.warning("Document pk=%d parsing failed: %s", document.pk, exc)
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            document.status = CourseDocument.Status.ERROR
            document.error_message = f"Непредвиденная ошибка: {exc}"
            document.save(update_fields=['status', 'error_message'])
            logger.exception("Unexpected error parsing document pk=%d", document.pk)
            return Response(
                {'detail': 'Внутренняя ошибка при обработке файла.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            CourseDocumentDetailSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Modules'])
class ModuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return Module.objects.select_related('course__owner').prefetch_related('lessons')

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return ModuleWriteSerializer
        return ModuleSerializer


@extend_schema(tags=['Lessons'])
class LessonViewSet(viewsets.ModelViewSet):
    permission_classes = [IsEnrolledOrOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Lesson.objects.select_related('module__course__owner')
        # Students see only lessons in courses they are enrolled in or own
        enrolled_ids = Enrollment.objects.filter(user=user).values_list('course_id', flat=True)
        owned_ids = Course.objects.filter(owner=user).values_list('id', flat=True)
        accessible = set(enrolled_ids) | set(owned_ids)
        return Lesson.objects.filter(
            module__course_id__in=accessible
        ).select_related('module__course__owner')

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return LessonWriteSerializer
        return LessonSerializer

    def _reindex(self, lesson: Lesson) -> None:
        course_title = lesson.module.course.title
        try:
            index_lesson_content(lesson, course_title)
        except Exception:
            pass  # RAG failure must not break the API response

    def perform_create(self, serializer):
        lesson = serializer.save()
        self._reindex(lesson)

    def perform_update(self, serializer):
        lesson = serializer.save()
        self._reindex(lesson)


# ---------------------------------------------------------------------------
# Quiz & materials endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lesson_materials(request, lesson_id: int) -> Response:
    """GET /api/v1/lessons/<lesson_id>/materials/"""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    materials = LessonMaterial.objects.filter(lesson=lesson)
    return Response(LessonMaterialSerializer(materials, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lesson_quiz(request, lesson_id: int) -> Response:
    """GET /api/v1/lessons/<lesson_id>/quiz/"""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    quiz = get_object_or_404(
        Quiz.objects.prefetch_related('questions__choices'),
        lesson=lesson,
    )
    return Response(QuizSerializer(quiz).data)


_PASS_THRESHOLD = 50  # score_percent >= threshold → is_passed


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz(request, quiz_id: int) -> Response:
    """
    POST /api/v1/quizzes/<quiz_id>/submit/
    Body: {"answers": {"<question_id>": [<choice_id>, ...], ...}}

    Progress is persisted in two places (both live in the analytics app):
      - QuizAttempt: immutable per-attempt record.
      - UserLessonProgress: mutable aggregate that the ML pipeline reads.
    We deliberately avoid a third StudentProgress table to prevent divergence.
    """
    quiz = get_object_or_404(
        Quiz.objects.select_related('lesson').prefetch_related('questions__choices'),
        pk=quiz_id,
    )
    answers = request.data.get('answers', {})
    if not isinstance(answers, dict):
        return Response(
            {'detail': 'Поле answers должно быть объектом.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    correct_count = 0
    total = 0
    for question in quiz.questions.all():
        total += 1
        submitted = set(answers.get(str(question.pk), []))
        correct = set(
            question.choices
            .filter(is_correct=True)
            .values_list('id', flat=True)
        )
        if submitted == correct:
            correct_count += 1

    score_percent = round(correct_count / total * 100) if total else 0
    is_passed = score_percent >= _PASS_THRESHOLD

    # --- Persist progress ---
    lesson = quiz.lesson

    # Immutable attempt log (used by ML for training data)
    QuizAttempt.objects.create(
        user=request.user,
        lesson=lesson,
        score=score_percent / 100,
    )

    # Mutable aggregate (read by ML inference and analytics dashboard)
    from django.db.models import F
    progress, created = UserLessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson,
        defaults={
            'quiz_score': score_percent / 100,
            'is_completed': is_passed,
            'attempt_count': 1,
        },
    )
    if not created:
        progress.quiz_score = score_percent / 100
        progress.is_completed = is_passed
        progress.attempt_count = F('attempt_count') + 1
        progress.save(update_fields=['quiz_score', 'is_completed', 'attempt_count', 'completed_at'])

    # --- Adaptive recommendation ---
    recommended_action = ''
    if not is_passed:
        first_material = (
            LessonMaterial.objects
            .filter(lesson=lesson)
            .order_by('uploaded_at')
            .values_list('title', flat=True)
            .first()
        )
        if first_material:
            recommended_action = (
                f'Рекомендуется повторить материал «{first_material}» '
                'перед следующей попыткой'
            )
        else:
            recommended_action = (
                'Рекомендуется повторить материалы текущего урока перед следующей попыткой'
            )

    return Response({
        'correct_answers': correct_count,
        'total_questions': total,
        'score_percent': score_percent,
        'is_passed': is_passed,
        'needs_review': not is_passed,
        'recommended_action': recommended_action,
    })


# --- TEMPLATE VIEWS ---
class CourseListTemplateView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'


class CourseDetailTemplateView(DetailView):
    queryset = (
        Course.objects
        .select_related('owner')
        .prefetch_related('modules__lessons')
    )
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            total_lessons = Lesson.objects.filter(module__course=self.object).count()

            completed_lessons = UserLessonProgress.objects.filter(
                user=self.request.user,
                lesson__module__course=self.object,
                is_completed=True
            ).count()

            if total_lessons > 0:
                progress_percent = int((completed_lessons / total_lessons) * 100)
            else:
                progress_percent = 0

            context['progress_percent']= progress_percent

            context['completed_lesson_ids'] = UserLessonProgress.objects.filter(
                user=self.request.user,
                lesson__module__course=self.object,
                is_completed=True
            ).values_list('lesson_id', flat=True)

        return context

class LessonDetailTemplateView(DetailView):
    model = Lesson
    template_name = 'courses/lesson_detail.html'
    context_object_name = 'lesson'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            is_completed = UserLessonProgress.objects.filter(
                user=self.request.user,
                lesson=self.object,
                is_completed=True
            ).exists()
            context['is_completed'] = is_completed
        return context


class CourseCreateView(LoginRequiredMixin, CreateView):
    model = Course
    fields = ['title', 'description']
    template_name = 'courses/course_form.html'
    success_url = reverse_lazy('course-list-html')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
