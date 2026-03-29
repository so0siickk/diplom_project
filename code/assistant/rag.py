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

def ask_assistant(query):
    """
    Главная функция: принимает вопрос студента, возвращает ответ.
    """
    # 1. Берем векторную базу
    vectorstore = get_vectorstore()

    # 2. Настраиваем ретривер (поисковик)
    # search_kwargs={'k': 3} значит "найди 3 самых похожих куска текста"
    retriever = vectorstore.as_retriever(search_kwargs={'k':3})

    # 3. Готовим промпт (инструкцию для AI)
    # Важно явно сказать "Отвечай на русском", так как модель англоязычная
    template = """
        Ты — умный помощник преподавателя. Твоя задача — отвечать на вопросы студентов 
        исключительно на основе предоставленного контекста из лекций.

        Контекст:
        {context}

        Вопрос студента: {question}

        Если ответа нет в контексте, скажи "В лекциях об этом не говорится".
        Отвечай вежливо и только на русском языке.

        Ответ:
        """

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