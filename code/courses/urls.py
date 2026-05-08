from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourseListTemplateView, CourseDetailTemplateView,
    LessonDetailTemplateView, CourseCreateView,
    CourseViewSet, ModuleViewSet, LessonViewSet,
    lesson_materials, lesson_quiz, submit_quiz,
)

router = DefaultRouter()
router.register(r'courses',  CourseViewSet,  basename='course')
router.register(r'modules',  ModuleViewSet,  basename='module')
router.register(r'lessons',  LessonViewSet,  basename='lesson')

urlpatterns = [
    # REST API — full CRUD for courses, modules, lessons
    # GET/POST   /api/v1/courses/
    # GET/PUT/PATCH/DELETE /api/v1/courses/<pk>/
    # (same pattern for /modules/ and /lessons/)
    path('api/v1/', include(router.urls)),

    # Quiz & materials
    path('api/v1/lessons/<int:lesson_id>/materials/', lesson_materials, name='lesson-materials'),
    path('api/v1/lessons/<int:lesson_id>/quiz/',      lesson_quiz,      name='lesson-quiz'),
    path('api/v1/quizzes/<int:quiz_id>/submit/',      submit_quiz,      name='quiz-submit'),

    # HTML template pages
    path('',                  CourseListTemplateView.as_view(),   name='course-list-html'),
    path('courses/<int:pk>/', CourseDetailTemplateView.as_view(), name='course-detail-html'),
    path('lessons/<int:pk>/', LessonDetailTemplateView.as_view(), name='lesson-detail-html'),
    path('create-course/',    CourseCreateView.as_view(),         name='course-create'),
]
