from rest_framework import serializers

from .models import AIEvaluation, AssignmentSubmission, CodeSubmission, EssaySubmission, OpenAssignment


# ---------------------------------------------------------------------------
# AIEvaluation
# ---------------------------------------------------------------------------

class AIEvaluationSerializer(serializers.ModelSerializer):
    """Только чтение: встраивается в ответ для преподавателя."""

    class Meta:
        model = AIEvaluation
        fields = [
            "id",
            "score",
            "feedback",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
            "evaluated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# OpenAssignment — READ (студент не видит reference_answer)
# ---------------------------------------------------------------------------

class OpenAssignmentSerializer(serializers.ModelSerializer):
    """
    Сериализатор для студентов и публичного отображения.
    Поле reference_answer намеренно исключено.
    """

    created_by = serializers.CharField(source="created_by.username", read_only=True)
    lesson_title = serializers.CharField(
        source="lesson.title", read_only=True, default=None
    )

    class Meta:
        model = OpenAssignment
        fields = [
            "id",
            "lesson",
            "lesson_title",
            "created_by",
            "title",
            "description",
            "max_score",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "lesson_title", "created_at"]


# ---------------------------------------------------------------------------
# OpenAssignment — WRITE и детальное чтение для преподавателя
# ---------------------------------------------------------------------------

class OpenAssignmentWriteSerializer(serializers.ModelSerializer):
    """
    POST / PUT / PATCH от преподавателя. Включает reference_answer.
    created_by устанавливается автоматически в perform_create.
    """

    class Meta:
        model = OpenAssignment
        fields = [
            "id",
            "lesson",
            "title",
            "description",
            "reference_answer",
            "max_score",
            "is_active",
        ]
        read_only_fields = ["id"]


class OpenAssignmentDetailTeacherSerializer(OpenAssignmentSerializer):
    """
    Детальный GET для преподавателя — добавляет reference_answer.
    Используется только в эндпоинтах с IsTeacher.
    """

    class Meta(OpenAssignmentSerializer.Meta):
        fields = OpenAssignmentSerializer.Meta.fields + ["reference_answer", "updated_at"]


# ---------------------------------------------------------------------------
# AssignmentSubmission — создание (студент отправляет ответ)
# ---------------------------------------------------------------------------

class SubmissionCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/assignments/{id}/submit/

    Студент передаёт только текст ответа. assignment и student
    устанавливаются во view.
    """

    class Meta:
        model = AssignmentSubmission
        fields = ["answer_text"]

    def validate_answer_text(self, value: str) -> str:
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Ответ слишком короткий. Минимум 10 символов."
            )
        return value.strip()


# ---------------------------------------------------------------------------
# AssignmentSubmission — просмотр студентом собственного ответа
# ---------------------------------------------------------------------------

class SubmissionStudentSerializer(serializers.ModelSerializer):
    """
    GET /api/v1/assignments/{id}/my-submission/
    Студент видит свой ответ, статус и AI-фидбек (если уже проверено).
    """

    ai_evaluation = AIEvaluationSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "answer_text",
            "submitted_at",
            "status",
            "status_display",
            "final_score",
            "teacher_comment",
            "ai_evaluation",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# AssignmentSubmission — список ответов для преподавателя
# ---------------------------------------------------------------------------

class SubmissionReviewSerializer(serializers.ModelSerializer):
    """
    GET /api/v1/assignments/{id}/submissions/
    Преподаватель видит ответы студентов с AI-оценкой.
    """

    ai_evaluation = AIEvaluationSerializer(read_only=True)
    student_username = serializers.CharField(source="student.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "student_username",
            "answer_text",
            "submitted_at",
            "status",
            "status_display",
            "ai_evaluation",
            "final_score",
            "teacher_comment",
        ]
        read_only_fields = [
            "id",
            "student_username",
            "answer_text",
            "submitted_at",
            "status",
            "status_display",
            "ai_evaluation",
        ]


# ---------------------------------------------------------------------------
# AssignmentSubmission — утверждение итогового балла преподавателем
# ---------------------------------------------------------------------------

class SubmissionApproveSerializer(serializers.ModelSerializer):
    """
    PATCH /api/v1/submissions/{id}/approve/

    Преподаватель указывает final_score и опциональный комментарий.
    Поле final_score обязательно.
    """

    class Meta:
        model = AssignmentSubmission
        fields = ["final_score", "teacher_comment"]

    def validate_final_score(self, value: int) -> int:
        submission: AssignmentSubmission = self.instance
        if submission and value > submission.assignment.max_score:
            raise serializers.ValidationError(
                f"Балл не может превышать максимум задания ({submission.assignment.max_score})."
            )
        return value

    def update(self, instance: AssignmentSubmission, validated_data: dict) -> AssignmentSubmission:
        instance.final_score = validated_data["final_score"]
        instance.teacher_comment = validated_data.get("teacher_comment", instance.teacher_comment)
        instance.status = AssignmentSubmission.Status.APPROVED
        instance.save(update_fields=["final_score", "teacher_comment", "status"])
        return instance


# ---------------------------------------------------------------------------
# CodeSubmission serializers
# ---------------------------------------------------------------------------

class CodeSubmitSerializer(serializers.Serializer):
    """
    POST /api/v1/code-assignments/{id}/submit/
    Студент передаёт только код. Остальное заполняется сервисом.
    """
    code_content = serializers.CharField(
        min_length=1,
        trim_whitespace=False,
        help_text='Исходный код Python для выполнения.',
    )


class CodeSubmissionSerializer(serializers.ModelSerializer):
    """
    Ответ после submit и для list/retrieve.
    Включает uuid, статус выполнения, вывод и фидбек AI.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)

    class Meta:
        model = CodeSubmission
        fields = [
            'uuid',
            'assignment',
            'assignment_title',
            'code_content',
            'status',
            'status_display',
            'output',
            'ai_feedback',
            'score',
            'submitted_at',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# EssaySubmission serializers
# ---------------------------------------------------------------------------

class EssaySubmitSerializer(serializers.Serializer):
    """
    POST /api/v1/essay-assignments/{id}/submit/
    Студент передаёт только текст ответа.
    """
    text_content = serializers.CharField(
        help_text='Письменный ответ на задание (минимум 10 слов).',
    )

    def validate_text_content(self, value: str) -> str:
        value = value.strip()
        if len(value.split()) < 10:
            raise serializers.ValidationError(
                'Эссе должно содержать минимум 10 слов.'
            )
        return value


class EssaySubmissionSerializer(serializers.ModelSerializer):
    """
    Ответ после submit и для list/retrieve.
    Содержит текст ответа, оценку AI и фидбек.
    """
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)

    class Meta:
        model = EssaySubmission
        fields = [
            'id',
            'assignment',
            'assignment_title',
            'text_content',
            'ai_feedback',
            'score',
            'created_at',
        ]
        read_only_fields = fields
