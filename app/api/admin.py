from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from typing import Optional

from app.database.connection import get_db
from app.configuration.security.dependencies import get_admin_user
from app.models.user import User, UserRole
from app.models.branch import Branch
from app.models.restaurant import Restaurant
from app.models.order import Order, OrderItem
from app.service.auth_service import AuthService

router = APIRouter()


# --------------------------
# HELPER: Admin-ға бекітілген ресторанды алу
# --------------------------
def get_admin_restaurant(db: Session, admin_id: int) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.admin_id == admin_id).first()
    if not restaurant:
        raise HTTPException(
            status_code=403,
            detail="Сізге ресторан тағайындалмаған"
        )
    return restaurant


# --------------------------
# BRANCH CRUD
# --------------------------
class BranchCreate(BaseModel):
    name: str
    address: str
    phone: str | None = None


@router.post("/branches", status_code=201)
def create_branch(
        branch: BranchCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = db.query(Restaurant).filter(Restaurant.admin_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=403,
            detail="Сізге ресторан тағайындалмаған"
        )

    branch_obj = Branch(
        name=branch.name,
        address=branch.address,
        phone=branch.phone,
        restaurant_id=restaurant.id
    )
    db.add(branch_obj)
    db.commit()
    db.refresh(branch_obj)
    return branch_obj


@router.get("/branches")
def get_my_branches(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = db.query(Restaurant).filter(Restaurant.admin_id == current_user.id).first()
    if not restaurant:
        return []
    branches = db.query(Branch).filter(Branch.restaurant_id == restaurant.id).all()
    return branches


@router.put("/branches/{branch_id}")
def update_branch(
        branch_id: int,
        name: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        is_active: bool | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.restaurant_id == restaurant.id
    ).first()

    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")

    if name: branch.name = name
    if address: branch.address = address
    if phone: branch.phone = phone
    if is_active is not None: branch.is_active = is_active

    db.commit()
    db.refresh(branch)
    return branch


@router.delete("/branches/{branch_id}")
def delete_branch(
        branch_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.restaurant_id == restaurant.id
    ).first()

    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")

    db.delete(branch)
    db.commit()
    return {"message": "Филиал өшірілді"}


# --------------------------
# CANTEEN ADMIN CRUD
# --------------------------
class CanteenAdminCreate(BaseModel):
    full_name: str
    email: str
    password: str
    branch_id: int


@router.post("/canteen-admins", status_code=201)
def create_canteen_admin(
        admin: CanteenAdminCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)

    branch = db.query(Branch).filter(
        Branch.id == admin.branch_id,
        Branch.restaurant_id == restaurant.id
    ).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")

    if db.query(User).filter(User.email == admin.email).first():
        raise HTTPException(status_code=400, detail="Email тіркелген")

    hashed_password = AuthService.get_password_hash(admin.password)
    canteen_admin = User(
        full_name=admin.full_name,
        email=admin.email,
        hashed_password=hashed_password,
        role=UserRole.CANTEEN_ADMIN,
        branch_id=admin.branch_id
    )

    db.add(canteen_admin)
    db.commit()
    db.refresh(canteen_admin)
    return canteen_admin


@router.get("/canteen-admins")
def get_canteen_admins(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = db.query(Restaurant).filter(Restaurant.admin_id == current_user.id).first()
    if not restaurant:
        return []
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    admins = db.query(User).filter(
        User.role == UserRole.CANTEEN_ADMIN,
        User.branch_id.in_(branch_ids)
    ).all()
    return admins


@router.delete("/canteen-admins/{admin_id}")
def delete_canteen_admin(
        admin_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)

    admin = db.query(User).filter(User.id == admin_id, User.role == UserRole.CANTEEN_ADMIN).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Администратор табылмады")

    branch = db.query(Branch).filter(Branch.id == admin.branch_id).first()
    if not branch or branch.restaurant_id != restaurant.id:
        raise HTTPException(status_code=403, detail="Қол жеткізу рұқсат етілмеген")

    db.delete(admin)
    db.commit()
    return {"message": "Администратор өшірілді"}


# ===== FOOD MANAGEMENT (REGULAR) =====

class CreateRegularFoodRequest(BaseModel):
    name: str
    description: str | None = None
    price: float
    calories: int | None = None
    ingredients: str | None = None
    image_url: str | None = None

@router.post("/foods", status_code=201)
def create_regular_food(
    food_data: CreateRegularFoodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Жалпы сатылымға арналған жаңа тағам қосу (Кәдімгі мәзір)"""
    from app.models.food import Food, MenuType
    
    restaurant = get_admin_restaurant(db, current_user.id)
    food = Food(
        name=food_data.name,
        description=food_data.description,
        price=food_data.price,
        calories=food_data.calories,
        ingredients=food_data.ingredients,
        image_url=food_data.image_url,
        menu_type=MenuType.REGULAR,
        restaurant_id=restaurant.id
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    
    return {
        "id": food.id,
        "name": food.name,
        "description": food.description,
        "price": food.price,
        "calories": food.calories,
        "ingredients": food.ingredients,
        "image_url": food.image_url,
        "menu_type": food.menu_type.value
    }

@router.get("/foods")
def get_regular_foods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Админнің ресторанына тиесілі барлық кәдімгі тағамдарды алу"""
    from app.models.food import Food, MenuType
    
    restaurant = get_admin_restaurant(db, current_user.id)
    foods = db.query(Food).filter(
        Food.restaurant_id == restaurant.id,
        Food.menu_type == MenuType.REGULAR
    ).all()
    
    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "price": f.price,
            "calories": f.calories,
            "ingredients": f.ingredients,
            "image_url": f.image_url,
            "menu_type": f.menu_type.value
        }
        for f in foods
    ]

class UpdateRegularFoodRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    calories: int | None = None
    ingredients: str | None = None
    image_url: str | None = None

@router.put("/foods/{food_id}")
def update_regular_food(
    food_id: int,
    food_data: UpdateRegularFoodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Кәдімгі тағамды жаңарту"""
    from app.models.food import Food, MenuType
    
    restaurant = get_admin_restaurant(db, current_user.id)
    food = db.query(Food).filter(
        Food.id == food_id,
        Food.restaurant_id == restaurant.id,
        Food.menu_type == MenuType.REGULAR
    ).first()
    
    if not food:
        raise HTTPException(status_code=404, detail="Тағам табылмады немесе бұл ресторанға тиесілі емес")
        
    for k, v in food_data.model_dump(exclude_unset=True).items():
        setattr(food, k, v)
        
    db.commit()
    db.refresh(food)
    
    return {
        "id": food.id,
        "name": food.name,
        "description": food.description,
        "price": food.price,
        "calories": food.calories,
        "ingredients": food.ingredients,
        "image_url": food.image_url,
        "menu_type": food.menu_type.value
    }

@router.delete("/foods/{food_id}")
def delete_regular_food(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Кәдімгі тағамды өшіру"""
    from app.models.food import Food, MenuType
    
    restaurant = get_admin_restaurant(db, current_user.id)
    food = db.query(Food).filter(
        Food.id == food_id,
        Food.restaurant_id == restaurant.id,
        Food.menu_type == MenuType.REGULAR
    ).first()
    
    if not food:
        raise HTTPException(status_code=404, detail="Тағам табылмады немесе бұл ресторанға тиесілі емес")
        
    db.delete(food)
    db.commit()
    return {"message": "Тағам өшірілді"}