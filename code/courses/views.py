from drf_spectacular.utils import extend_schema
from rest_framework import generics
from django.views.generic import ListView, DetailView
from .models import Course, Lesson
from .serializers import CourseSerializer
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from analytics.models import UserLessonProgress


# --- API VIEWS ---
_COURSE_QUERYSET = (
    Course.objects
    .select_related('owner')
    .prefetch_related('modules__lessons')
)


@extend_schema(tags=['Courses'], summary='List all courses with modules and lessons')
class CourseListView(generics.ListAPIView):
    queryset = _COURSE_QUERYSET
    serializer_class = CourseSerializer


@extend_schema(tags=['Courses'], summary='Retrieve a single course by ID')
class CourseDetailView(generics.RetrieveAPIView):
    queryset = _COURSE_QUERYSET
    serializer_class = CourseSerializer


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
