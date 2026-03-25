from typing import Annotated

import aiohttp
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
import secrets
import string

from config import settings
from app.configuration.auth_generate_google import generate_google_auth
from app.configuration.state_storage import state_storage
from app.database.connection import get_db
from app.models.user import User
from app.models.otp_code import OtpCode
from app.schemas.auth_dto import (
    UserRegisterRequest, 
    UserLoginRequest, 
    UserUpdateRequest,
    TokenResponse, 
    UserResponse,
    SendOtpRequest,
    VerifyOtpRequest,
    TokenRefreshRequest,
    ChangePasswordRequest,
    ChangeEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from app.service.mail_service import MailService
from app.service.auth_service import AuthService
from app.configuration.security.dependencies import get_current_active_user
from datetime import datetime, timedelta

router = APIRouter()


def generate_random_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.get("/google/url")
async def get_google_auth():
    url = generate_google_auth()
    return RedirectResponse(url=url,status_code=302)


@router.post("/google/callback", response_model=TokenResponse)
async def google_auth_callback(
    code: Annotated[str, Body()],
    state: Annotated[str, Body()],
    db: Session = Depends(get_db),
):
    if state not in state_storage:
        raise HTTPException(status_code=400, detail="Invalid state")

    google_token_url = "https://oauth2.googleapis.com/token"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=google_token_url,
            data={
                "client_id": settings.AUTH_GOOGLE_CLIENT_ID,
                "client_secret": settings.AUTH_GOOGLE_SECRET_ID,
                "redirect_uri": "http://localhost:3000/google/auth",
                "grant_type": "authorization_code",
                "code": code,
            },
        ) as response:
            res = await response.json()

    id_token = res.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Google token error")

    # ❗ Signature verify қазір skip, бірақ audience тексереміз
    user_data = jwt.decode(
        id_token,
        options={"verify_signature": False},
        audience=settings.AUTH_GOOGLE_CLIENT_ID,
    )

    email = user_data.get("email")
    full_name = user_data.get("name", "Google User")

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    # 🔎 USER ІЗДЕУ
    user = db.query(User).filter(User.email == email).first()

    # 🆕 Егер жоқ болса → REGISTER
    if not user:
        random_password = generate_random_password()
        user = AuthService.register_user(
            db=db,
            full_name=full_name,
            email=email,
            password=random_password,
            is_email_verified=True
        )

    access_token = AuthService.create_access_token({"sub": user.id, "role": user.role.value})
    refresh_token = AuthService.create_refresh_token({"sub": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

@router.post("/send-otp")
async def send_otp(data: SendOtpRequest, db: Session = Depends(get_db)):
    # 1. Генерация OTP
    otp_code = "".join(secrets.choice(string.digits) for _ in range(6))
    
    # 2. Сақтау
    db_otp = OtpCode(
        email=data.email,
        code=otp_code,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(db_otp)
    db.commit()
    
    # 3. Жіберу
    try:
        MailService.send_otp_email(data.email, otp_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email жіберу қатесі: {str(e)}")
        
    return {"message": "OTP коды жіберілді"}

@router.post("/verify-otp")
async def verify_otp(data: VerifyOtpRequest, db: Session = Depends(get_db)):
    otp = db.query(OtpCode).filter(
        OtpCode.email == data.email,
        OtpCode.code == data.code
    ).order_by(OtpCode.created_at.desc()).first()
    
    if not otp or otp.is_expired():
        raise HTTPException(status_code=400, detail="Код қате немесе мерзімі өткен")
    
    # OTP-ны расталды деп белгілейміз (немесе өшіреміз)
    # Қазірше өшіре салсақ та болады, бірақ register-де тексеру үшін керек
    # Сондықтан жаңа өріс қосайық немесе User-ді алдын-ала жасайық
    
    user = db.query(User).filter(User.email == data.email).first()
    if user:
        user.is_email_verified = True
    else:
        # User жоқ болса, бұл жаңа тіркелу. 
        # Register кезінде қалай тексереміз? 
        # OTP кестесінде verified=True қылып қалдырайық.
        otp.code = "VERIFIED" # арнайы белгі
    
    db.commit()
    return {"message": "Email сәтті расталды", "verified": True}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegisterRequest, db: Session = Depends(get_db)):
    # Email расталғанын тексеру
    otp = db.query(OtpCode).filter(
        OtpCode.email == user_data.email,
        OtpCode.code == "VERIFIED"
    ).first()
    
    if not otp:
        raise HTTPException(status_code=400, detail="Email расталмаған. Кодты тексеріңіз.")

    try:
        user = AuthService.register_user(
            db=db,
            full_name=user_data.full_name,
            email=user_data.email,
            password=user_data.password,
            is_email_verified=True
        )
        # Тіркелгеннен кейін OTP-ны өшіреміз
        db.delete(otp)
        user.is_email_verified = True
        db.commit()
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


    access_token = AuthService.create_access_token({"sub": user.id, "role": user.role.value})
    refresh_token = AuthService.create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLoginRequest, db: Session = Depends(get_db)):
    """Жүйеге кіру (логин)"""
    user = AuthService.authenticate_user(
        db=db,
        email=credentials.email,
        password=credentials.password
    )
    
    # Токендер жасау
    access_token = AuthService.create_access_token({"sub": user.id, "role": user.role.value})
    refresh_token = AuthService.create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: TokenRefreshRequest, db: Session = Depends(get_db)):
    """Token жаңарту"""
    try:
        payload = AuthService.decode_token(data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token қате"
            )
        
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Қолданушы табылмады"
            )
        
        # Жаңа токендер жасау
        new_access_token = AuthService.create_access_token({"sub": user.id, "role": user.role.value})
        new_refresh_token = AuthService.create_refresh_token({"sub": user.id})
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token жарамсыз"
        )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Ағымдағы қолданушы ақпаратын алу"""
    return current_user

@router.put("/me", response_model=UserResponse)
def update_me(data: UserUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Update current user's profile"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update only provided fields
    for field, value in data.__dict__.items():
        if value is not None and hasattr(user, field):
            setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@router.post("/me/change-password")
def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Change current user's password"""
    if not AuthService.verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Қазіргі құпиясөз қате")
    
    current_user.hashed_password = AuthService.get_password_hash(data.new_password)
    db.commit()
    return {"message": "Құпиясөз сәтті өзгертілді"}

@router.post("/me/change-email/send-otp")
async def send_change_email_otp(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # ForgotPasswordRequest reused here as it only needs 'email'
    # We shouldn't let them easily change to an existing email unconditionally, but we'll check it here.
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Бұл email бос емес")

    otp_code = "".join(secrets.choice(string.digits) for _ in range(6))
    db_otp = OtpCode(email=data.email, code=otp_code, expires_at=datetime.utcnow() + timedelta(minutes=10))
    db.add(db_otp)
    db.commit()
    
    try:
        MailService.send_otp_email(data.email, otp_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email жіберу қатесі: {str(e)}")
        
    return {"message": "Растау коды жаңа email-ға жіберілді"}

@router.post("/me/change-email/verify")
def verify_change_email(data: ChangeEmailRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    otp = db.query(OtpCode).filter(OtpCode.email == data.new_email, OtpCode.code == data.otp_code).order_by(OtpCode.created_at.desc()).first()
    if not otp or otp.is_expired():
        raise HTTPException(status_code=400, detail="Код қате немесе мерзімі өткен")
    
    existing_user = db.query(User).filter(User.email == data.new_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Бұл email бос емес")

    current_user.email = data.new_email
    db.delete(otp)
    db.commit()
    return {"message": "Email сәтті өзгертілді"}

@router.post("/forgot-password")
async def send_forgot_password_otp(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Бұл email жүйеде тіркелмеген")

    otp_code = "".join(secrets.choice(string.digits) for _ in range(6))
    db_otp = OtpCode(email=data.email, code=otp_code, expires_at=datetime.utcnow() + timedelta(minutes=10))
    db.add(db_otp)
    db.commit()
    
    try:
        MailService.send_password_reset_email(data.email, otp_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email жіберу қатесі: {str(e)}")
        
    return {"message": "Растау коды email-ға жіберілді"}

@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Бұл email жүйеде тіркелмеген")

    otp = db.query(OtpCode).filter(OtpCode.email == data.email, OtpCode.code == data.otp_code).order_by(OtpCode.created_at.desc()).first()
    if not otp or otp.is_expired():
        raise HTTPException(status_code=400, detail="Код қате немесе мерзімі өткен")

    user.hashed_password = AuthService.get_password_hash(data.new_password)
    db.delete(otp)
    db.commit()
    
    return {"message": "Құпиясөз сәтті қалпына келтірілді"}

@router.post("/logout")
def logout(current_user: User = Depends(get_current_active_user)):
    """Жүйеден шығу"""
    # Client-тегі токенді өшіру керек
    return {"message": "Сәтті шықтыңыз"} 
