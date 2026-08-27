class AppException(Exception):
    """Базовое доменное исключение"""

    pass


# 403
class ForbiddenError(AppException):
    def __init__(self, detail: str = "Forbidden"):
        self.detail = detail


# 404
class NotFoundError(AppException):
    def __init__(self, detail: str = "Not found"):
        self.detail = detail


# 400 — невалидные данные, неверное состояние
class BadRequestError(AppException):
    def __init__(self, detail: str = "Bad request"):
        self.detail = detail


# 409 — конфликт, дубликат, уже существует
class ConflictError(AppException):
    def __init__(self, detail: str = "Conflict"):
        self.detail = detail


# 402 — недостаточно средств и т.п.
class PaymentRequiredError(AppException):
    def __init__(self, detail: str = "Payment required"):
        self.detail = detail


# 401 - ошибка авторизации
class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Ошибка авторизации"):
        self.detail = detail


# 429 — слишком часто (лимит запросов)
class TooManyRequestsError(AppException):
    def __init__(self, detail: str = "Слишком много запросов"):
        self.detail = detail


# 503 — внешний сервис (биржа) не ответил; запрос сам по себе валиден
class ServiceUnavailableError(AppException):
    def __init__(self, detail: str = "Сервис временно недоступен"):
        self.detail = detail
