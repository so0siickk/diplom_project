from django.urls import path
from .views import (
    CourseListView, CourseDetailView,  # API views
    CourseListTemplateView, CourseDetailTemplateView, LessonDetailTemplateView, CourseCreateView  # Template views
)

urlpatterns = [
    # API endpoints (JSON)
    path('api/v1/courses/', CourseListView.as_view(), name='course-list-api'),
    path('api/v1/courses/<int:pk>/', CourseDetailView.as_view(), name='course-detail-api'),

    # Frontend pages (HTML) - "морда" сайта
    path('', CourseListTemplateView.as_view(), name='course-list-html'),
    path('courses/<int:pk>/', CourseDetailTemplateView.as_view(), name='course-detail-html'),
    path('lessons/<int:pk>/', LessonDetailTemplateView.as_view(), name='lesson-detail-html'),
    path('create-course/', CourseCreateView.as_view(), name='course-create'),
]