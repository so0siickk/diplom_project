from django.urls import path
from .views import chat_api

urlpatterns = [
    path('api/v1/chat/', chat_api, name='chat_api'),
]