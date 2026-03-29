from django.urls import path
from .views import complete_lesson, recommendations_api

urlpatterns = [
    path('complete/<int:lesson_id>/', complete_lesson, name='complete-lesson'),
    path('api/recommendations/<int:course_id>/', recommendations_api, name='recommendations-api'),
]
