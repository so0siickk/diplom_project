from django.conf import settings
from langchain_gigachat.chat_models import GigaChat
from langchain_core.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from .vector_store import get_vectorstore


def get_llm():
    """
    Подключаемся к бесплатной модели на HuggingFace.
    repo_id - это ID модели. Zephyr-7b - легкая и хорошо понимает инструкции.
    """
    return GigaChat(
        credentials=settings.GIGACHAT_AUTHORIZATION_KEY,
        model="GigaChat",
        verify_ssl_certs=False,
        temperature=0.1,
    )

def ask_assistant(query, lesson_id=None):
    """
    Главная функция: принимает вопрос студента, возвращает ответ.
    """
    # 1. Берем векторную базу
    vectorstore = get_vectorstore()

    search_kwargs = {'k': 4}

    if lesson_id:
        # lesson_id is stored as a string in ChromaDB metadata (see vector_store.py)
        search_kwargs['filter'] = {'lesson_id': str(lesson_id)}

    # 2. Настраиваем ретривер (поисковик)
    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)

    # 3. Готовим промпт (инструкцию для AI)
    # Важно явно сказать "Отвечай на русском", так как модель англоязычная
    # template = """
    #     Ты — умный помощник преподавателя. Твоя задача — отвечать на вопросы студентов
    #     исключительно на основе предоставленного контекста из лекций.
    #
    #     Контекст:
    #     {context}
    #
    #     Вопрос студента: {question}
    #
    #     Если ответа нет в контексте, скажи "В лекциях об этом не говорится".
    #     Отвечай вежливо и только на русском языке.
    #
    #     Ответ:
    #     """

    template = """
    Ты — ИИ-ассистент. Твоя единственная цель — ответить на вопрос студента, используя ТОЛЬКО факты из предоставленного текста.

    ТЕКСТ ЛЕКЦИИ:
    {context}

    ВОПРОС: {question}

    ЖЕСТКИЕ ПРАВИЛА:
    1. Отвечай СРАЗУ по существу. Никаких вступлений.
    2. ЗАПРЕЩЕНО писать фразы вроде "В лекциях прямо не говорится", "В тексте нет", "Исходя из текста".
    3. Если ответ можно логически вывести из кусков кода или примеров в тексте — делай это.
    4. Если текст ВООБЩЕ не относится к вопросу, напиши только одну фразу: "В материалах лекции нет информации об этом."

    ОТВЕТ:"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question"]
    )

    # 4. Собираем цепочку (Chain)
    qa_chain = RetrievalQA.from_chain_type(
        llm=get_llm(),
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt":prompt}
    )

    # 5. Запускаем
    result = qa_chain.invoke({"query":query})

    return result['result']