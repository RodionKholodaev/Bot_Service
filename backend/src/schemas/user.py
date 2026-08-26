from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    # Галочки с формы регистрации. Значение по умолчанию False, а не
    # обязательное поле: «галочку не поставили» и «клиент вообще не прислал
    # поле» — это одно и то же «не согласен», и отвечать на это надо понятным
    # русским текстом из AuthService, а не массивом ошибок 422 от pydantic.
    # Обязательность проверяет AuthService — см. _collect_consents().
    accept_terms: bool = False
    accept_pdn: bool = False
    accept_cross_border: bool = False
    # Реклама требует отдельного согласия (ст. 18 ФЗ «О рекламе»), поэтому
    # чекбокс отдельный и необязательный — на регистрацию он не влияет.
    accept_marketing: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 token type constant, not a secret
    user_id: int
    username: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr

    model_config = {"from_attributes": True}
