from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.service import AuthService
from app.models.user import User, UserRole

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Ағымдағы қолданушыны алу"""
    token = credentials.credentials
    return AuthService.get_current_user(db, token)

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Белсенді қолданушыны алу"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Қолданушы белсенді емес"
        )
    return current_user

# Рөлдерді тексеру
def require_role(*allowed_roles: UserRole):
    """Рөлді тексеру decorator"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Қол жеткізу рұқсат етілмеген"
            )
        return current_user
    return role_checker

# Нақты рөлдер үшін dependencies
def get_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Admin"""
    if current_user.role != UserRole.ADMIN:
        print("dfsgbbdfv")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Admin қол жеткізе алады"
        )
    return current_user

def get_canteen_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Асхана администраторы"""
    if current_user.role not in [UserRole.ADMIN, UserRole.CANTEEN_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Асхана администраторы қол жеткізе алады"
        )
    return current_user

def get_cashier_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Кассир"""
    if current_user.role not in [UserRole.ADMIN, UserRole.CANTEEN_ADMIN, UserRole.CASHIER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Кассир қол жеткізе алады"
        )
    return current_user

def get_client_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Клиент"""
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Клиент қол жеткізе алады"
        )
    return current_user

def get_owner_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Owner"""
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Owner қол жеткізе алады"
        )
    return current_user

def get_restaurant_admin_user(restaurant_id: int, current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Admin және қолданушының restaurant_id сәйкес келгенін тексеру"""
    if current_user.role != UserRole.ADMIN or current_user.restaurant_id != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Admin және қолданушының restaurant_id сәйкес келгенін қол жеткізе алады"
        )
    return current_user

def get_branch_admin_user(branch_id: int, current_user: User = Depends(get_current_active_user)) -> User:
    """Тек Асхана администраторы және қолданушының branch_id сәйкес келгенін тексеру"""
    if current_user.role not in [UserRole.ADMIN, UserRole.CANTEEN_ADMIN] or current_user.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тек Асхана администраторы және қолданушының branch_id сәйкес келгенін қол жеткізе алады"
        )
    return current_user
