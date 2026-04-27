from cryptography.fernet import Fernet
from src.config import settings

# Берём ключ из переменной окружения
_FERNET_KEY = settings.FERNET_KEY

if not _FERNET_KEY:
    raise RuntimeError(
        "Переменная окружения FERNET_KEY не задана. "
        "Сгенерируйте ключ: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

_fernet = Fernet(_FERNET_KEY.encode())


def encrypt(value: str) -> str:
    """Зашифровать строку. Результат — строка, безопасная для хранения в БД."""
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Расшифровать строку, полученную из encrypt()."""
    return _fernet.decrypt(value.encode()).decode()