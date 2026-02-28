from datetime import datetime, timedelta
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from config import settings
from fastapi import HTTPException, status

# Ескі bcrypt өшірілді
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ЖАҢА: Argon2 қолданамыз
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

class AuthService:
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Парольді тексеру"""
        try:
            ph.verify(hashed_password, plain_password)
            return True
        except VerifyMismatchError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Парольді хэштеу (Argon2)"""
        return ph.hash(password)  # Ұзындыққа шектеу жоқ!

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access"})
        if "sub" in to_encode:
            to_encode["sub"] = str(to_encode["sub"])
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        if "sub" in to_encode:
            to_encode["sub"] = str(to_encode["sub"])
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Token-ды декодтау"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token жарамсыз немесе мерзімі өткен"
            )
    
    @staticmethod
    def register_user(db: Session, full_name: str, email: str, password: str) -> User:
        """Жаңа клиент қолданушыны тіркеу"""
        # Email тексеру
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Бұл email тіркелген"
            )
        

        
        # Жаңа қолданушы жасау
        hashed_password = AuthService.get_password_hash(password)
        new_user = User(
            full_name=full_name,
            email=email,
            hashed_password=hashed_password,
            role=UserRole.CLIENT
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """Қолданушыны аутентификациялау"""
        user = db.query(User).filter(User.email == email).first()
        
        if not user or not AuthService.verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email немесе пароль қате"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Қолданушы белсенді емес"
            )
        
        return user
    
    @staticmethod
    def get_current_user(db: Session, token: str) -> User:
        """Ағымдағы қолданушыны алу"""
        payload = AuthService.decode_token(token)
        user_id: int = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Қолданушы табылмады"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Қолданушы табылмады"
            )
        
        return user