from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views.generic import ListView, DetailView
from .models import Course, Module, Lesson, Enrollment
from .serializers import (
    CourseSerializer, CourseWriteSerializer,
    ModuleSerializer, ModuleWriteSerializer,
    LessonSerializer, LessonWriteSerializer,
)
from .permissions import IsOwnerOrReadOnly, IsEnrolledOrOwner
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from analytics.models import UserLessonProgress
from assistant.vector_store import index_lesson_content


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
    @action(detail=True, methods=['post'], url_path='enroll')
    def enroll(self, request, pk=None):
        course = self.get_object()
        _, created = Enrollment.objects.get_or_create(user=request.user, course=course)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({'enrolled': True, 'created': created}, status=code)


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
