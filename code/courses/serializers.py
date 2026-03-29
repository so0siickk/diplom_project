from rest_framework import serializers
from .models import Course, Module, Lesson


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'video_url', 'order']


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)  # Вкладываем уроки внутрь модуля

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'lessons']


class CourseSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)  # Вкладываем модули внутрь курса

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'owner', 'created_at', 'modules']
