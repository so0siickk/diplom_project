import os
from dotenv import load_dotenv
from langchain_gigachat.chat_models import GigaChat

# 1. Загружаем ключ
load_dotenv()
token = os.getenv("GIGACHAT_AUTHORIZATION_KEY")

print(f"1. Ключ загружен. Длина: {len(token) if token else 0} символов.")
if token:
    print(f"   Начало ключа: {token[:10]}...")

# 2. Пробуем подключиться
print("\n2. Пробуем отправить запрос в GigaChat...")
try:
    chat = GigaChat(
        credentials=token,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_PERS" # Важно! У тебя на скрине именно этот scope
    )
    res = chat.invoke("Скажи 'Привет, диплом!'")
    print(f"\n✅ УСПЕХ! Ответ нейросети:\n{res.content}")
except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")