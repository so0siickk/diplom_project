from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .rag import ask_assistant


@extend_schema(
    tags=['Assistant'],
    summary='Ask the RAG assistant a question about course materials',
    request={'application/json': {'type': 'object', 'properties': {
        'question': {'type': 'string', 'example': 'What is gradient descent?'},
        'lesson_id': {'type': 'integer', 'example': 1},
    }, 'required': ['question']}},
    responses={200: {'type': 'object', 'properties': {
        'answer': {'type': 'string'},
    }}},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """RAG endpoint: accepts {"question": "..."} and returns an AI-generated answer."""
    question = request.data.get('question')
    lesson_id = request.data.get('lesson_id')
    if not question:
        return Response({"error": "Вопрос не задан"}, status=400)

    try:
        answer = ask_assistant(question, lesson_id=lesson_id)
        return Response({"answer": answer})
    except Exception as e:
        return Response({"error": str(e)}, status=500)