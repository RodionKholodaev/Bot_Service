# from fastapi import APIRouter, HTTPException, status
# from pydantic import BaseModel, EmailStr, field_validator
# from enum import Enum
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import os




# router = APIRouter(prefix="/support", tags=["support"])


# class SupportCategory(str, Enum):
#     technical = "technical"
#     billing   = "billing"
#     bots      = "bots"
#     other     = "other"


# CATEGORY_LABELS = {
#     SupportCategory.technical: "Техническая проблема",
#     SupportCategory.billing:   "Вопрос по оплате",
#     SupportCategory.bots:      "Работа ботов",
#     SupportCategory.other:     "Другое",
# }


# class SupportRequest(BaseModel):
#     name:     str
#     email:    EmailStr
#     category: SupportCategory
#     message:  str

#     @field_validator("name")
#     @classmethod
#     def name_not_empty(cls, v: str) -> str:
#         v = v.strip()
#         if not v:
#             raise ValueError("name cannot be empty")
#         return v

#     @field_validator("message")
#     @classmethod
#     def message_length(cls, v: str) -> str:
#         v = v.strip()
#         if not v:
#             raise ValueError("message cannot be empty")
#         if len(v) > 2000:
#             raise ValueError("message too long (max 2000 chars)")
#         return v


# # ── email helpers ──────────────────────────────────────────────────────────────

# SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
# SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
# SMTP_USER     = os.getenv("SMTP_USER")          # ваш ящик-отправитель
# SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")      # пароль / app-password
# SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")      # куда приходят обращения


# def _send_email(subject: str, html_body: str, reply_to: str) -> None:
#     """Отправить письмо через SMTP. Бросает исключение при ошибке."""
#     if not all([SMTP_USER, SMTP_PASSWORD, SUPPORT_EMAIL]):
#         raise RuntimeError("SMTP credentials are not configured")

#     msg = MIMEMultipart("alternative")
#     msg["Subject"]  = subject
#     msg["From"]     = SMTP_USER
#     msg["To"]       = SUPPORT_EMAIL
#     msg["Reply-To"] = reply_to
#     msg.attach(MIMEText(html_body, "html", "utf-8"))

#     with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
#         server.ehlo()
#         server.starttls()
#         server.login(SMTP_USER, SMTP_PASSWORD)
#         server.sendmail(SMTP_USER, SUPPORT_EMAIL, msg.as_string())


# def _build_html(req: SupportRequest) -> str:
#     category_label = CATEGORY_LABELS[req.category]
#     message_escaped = req.message.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
#     return f"""
#     <html><body style="font-family: sans-serif; background:#0a0e1a; color:#e4e7f0; padding:32px;">
#       <div style="max-width:600px; margin:0 auto; background:#1a1f35;
#                   border-radius:16px; padding:32px; border:1px solid rgba(255,255,255,0.08);">
#         <h2 style="color:#60a5fa; margin-bottom:24px;">
#           📩 Новое обращение в поддержку
#         </h2>
#         <table style="width:100%; border-collapse:collapse;">
#           <tr>
#             <td style="padding:10px 0; color:#9ca3af; width:140px;">Имя</td>
#             <td style="padding:10px 0; color:#e4e7f0; font-weight:600;">{req.name}</td>
#           </tr>
#           <tr>
#             <td style="padding:10px 0; color:#9ca3af;">Email</td>
#             <td style="padding:10px 0;">
#               <a href="mailto:{req.email}" style="color:#60a5fa;">{req.email}</a>
#             </td>
#           </tr>
#           <tr>
#             <td style="padding:10px 0; color:#9ca3af;">Категория</td>
#             <td style="padding:10px 0; color:#e4e7f0;">{category_label}</td>
#           </tr>
#         </table>
#         <hr style="border:none; border-top:1px solid rgba(255,255,255,0.07); margin:20px 0;">
#         <p style="color:#9ca3af; margin-bottom:8px; font-size:13px;">Сообщение:</p>
#         <div style="background:rgba(255,255,255,0.04); border-radius:10px;
#                     padding:16px; color:#e4e7f0; font-size:15px; line-height:1.7;">
#           {message_escaped}
#         </div>
#       </div>
#     </body></html>
#     """


# # ── endpoint ───────────────────────────────────────────────────────────────────

# @router.post("", status_code=status.HTTP_204_NO_CONTENT)
# async def send_support_message(req: SupportRequest) -> None:
#     """
#     Принять обращение пользователя и отправить email на ящик поддержки.

#     Body:
#         name     – имя пользователя
#         email    – email для ответа
#         category – техническая / биллинг / боты / другое
#         message  – текст обращения (до 2000 символов)
#     """
#     subject = f"[CryptoBot Support] {CATEGORY_LABELS[req.category]} — {req.name}"

#     try:
#         _send_email(
#             subject=subject,
#             html_body=_build_html(req),
#             reply_to=str(req.email),
#         )
#     except Exception as exc:
#         # Логируем ошибку, но не раскрываем детали SMTP клиенту
#         print(f"[support] email send failed: {exc}")
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail="Не удалось отправить сообщение. Попробуйте позже.",
#         )