import os

from rest_framework import serializers

from .models import Assignment, Choice, Course, CourseDocument, Lesson, LessonMaterial, Module, Question, Quiz
from .services.document_parser import ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# READ serializers — deeply nested, used for GET list/detail
# ---------------------------------------------------------------------------

class AssignmentSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(
        source='get_assignment_type_display', read_only=True
    )

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description',
            'assignment_type', 'type_label',
            'content', 'max_score', 'max_attempts', 'order',
        ]
        read_only_fields = ['id', 'type_label']


class LessonSerializer(serializers.ModelSerializer):
    # source='course_assignments' — реальный related_name в модели Assignment.
    # Без него DRF резолвит имя поля как 'assignments', что попадает
    # на OpenAssignment (assignments app), а не на courses.Assignment.
    assignments = AssignmentSerializer(source='course_assignments', many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'video_url', 'order', 'assignments']


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'lessons']


class CourseSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'owner', 'created_at', 'modules', 'is_enrolled']

    def get_is_enrolled(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        # Owners and admins always have full access — no enrollment needed
        if user.is_staff or obj.owner_id == user.pk:
            return True
        return obj.enrollments.filter(user=user).exists()


# ---------------------------------------------------------------------------
# WRITE serializers — flat, used for POST / PUT / PATCH
# ---------------------------------------------------------------------------

class CourseWriteSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/courses/
    { "title": "...", "description": "..." }
    owner is set automatically from request.user in perform_create.
    """
    class Meta:
        model = Course
        fields = ['id', 'title', 'description']
        read_only_fields = ['id']


class ModuleWriteSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/modules/
    { "course": 1, "title": "...", "description": "...", "order": 1 }
    """
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'description', 'order']
        read_only_fields = ['id']


class LessonWriteSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/lessons/
    { "module": 3, "title": "...", "content": "...", "video_url": null, "order": 1 }
    """
    module = serializers.PrimaryKeyRelatedField(queryset=Module.objects.select_related('course'))

    class Meta:
        model = Lesson
        fields = ['id', 'module', 'title', 'content', 'video_url', 'order']
        read_only_fields = ['id']


# ---------------------------------------------------------------------------
# CourseDocument serializers
# ---------------------------------------------------------------------------

class CourseDocumentListSerializer(serializers.ModelSerializer):
    """
    GET /api/v1/courses/{id}/documents/

    Лёгкий сериализатор для списка: не включает extracted_text,
    чтобы не перегружать сеть при отображении таблицы документов.
    """

    uploaded_by = serializers.CharField(source='uploaded_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CourseDocument
        fields = [
            'id',
            'original_filename',
            'status',
            'status_display',
            'error_message',
            'uploaded_by',
            'uploaded_at',
        ]
        read_only_fields = fields


class CourseDocumentUploadSerializer(serializers.Serializer):
    """
    POST /api/v1/courses/{id}/documents/

    Принимает multipart/form-data с полем file.
    Валидирует расширение до сохранения на диск.
    """

    file = serializers.FileField(
        help_text=f"Допустимые форматы: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
    )

    def validate_file(self, value):
        _, ext = os.path.splitext(value.name)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Формат «{ext}» не поддерживается. "
                f"Допустимые форматы: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )
        # Ограничение размера: 20 МБ
        max_size = 20 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Размер файла ({value.size // 1024 // 1024} МБ) превышает "
                f"допустимый предел 20 МБ."
            )
        return value


# ---------------------------------------------------------------------------
# Quiz serializers — is_correct is intentionally absent from ChoiceSerializer
# ---------------------------------------------------------------------------

class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'is_multiple_choice', 'choices']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'questions']


class LessonMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonMaterial
        fields = ['id', 'title', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


# ---------------------------------------------------------------------------


class CourseDocumentDetailSerializer(serializers.ModelSerializer):
    """
    Ответ после успешной загрузки: включает извлечённый текст
    (нужен фронтенду для предпросмотра результата парсинга).
    """

    uploaded_by = serializers.CharField(source='uploaded_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CourseDocument
        fields = [
            'id',
            'original_filename',
            'status',
            'status_display',
            'error_message',
            'extracted_text',
            'uploaded_by',
            'uploaded_at',
        ]
        read_only_fields = fields
