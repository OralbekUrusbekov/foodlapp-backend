from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.restaurant_dto import RestaurantCreate, RestaurantUpdate


class RestaurantService:

    @staticmethod
    def create_restaurant(db: Session, owner_id: int, restaurant_data: RestaurantCreate) -> Restaurant:
        """Жаңа ресторан жасау (тек Owner)"""
        restaurant = Restaurant(
            name=restaurant_data.name,
            description=restaurant_data.description,
            logo_url=restaurant_data.logo_url,
            owner_id=owner_id
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)
        return restaurant

    @staticmethod
    def get_owner_restaurants(db: Session, owner_id: int):
        """Owner-дің ресторандарын алу"""
        return db.query(Restaurant).filter(Restaurant.owner_id == owner_id).all()

    @staticmethod
    def update_restaurant(db: Session, restaurant_id: int, owner_id: int,
                          restaurant_data: RestaurantUpdate) -> Restaurant:
        """Ресторанды өзгерту"""
        restaurant = db.query(Restaurant).filter(
            Restaurant.id == restaurant_id,
            Restaurant.owner_id == owner_id
        ).first()

        if not restaurant:
            raise HTTPException(status_code=404, detail="Ресторан табылмады")

        if restaurant_data.name is not None:
            restaurant.name = restaurant_data.name
        if restaurant_data.description is not None:
            restaurant.description = restaurant_data.description
        if restaurant_data.logo_url is not None:
            restaurant.logo_url = restaurant_data.logo_url
        if restaurant_data.is_active is not None:
            restaurant.is_active = restaurant_data.is_active
        if restaurant_data.admin_id is not None:
            # Admin-ді тексеру
            admin = db.query(User).filter(
                User.id == restaurant_data.admin_id,
                User.role == UserRole.ADMIN
            ).first()
            if not admin:
                raise HTTPException(status_code=404, detail="Admin табылмады")
            restaurant.admin_id = restaurant_data.admin_id
            admin.restaurant_id = restaurant.id

        db.commit()
        db.refresh(restaurant)
        return restaurant

    @staticmethod
    def delete_restaurant(db: Session, restaurant_id: int, owner_id: int):
        """Ресторанды өшіру"""
        restaurant = db.query(Restaurant).filter(
            Restaurant.id == restaurant_id,
            Restaurant.owner_id == owner_id
        ).first()

        if not restaurant:
            raise HTTPException(status_code=404, detail="Ресторан табылмады")

        db.delete(restaurant)
        db.commit()
        return {"message": "Ресторан өшірілді"}

    @staticmethod
    def assign_admin(db: Session, restaurant_id: int, owner_id: int, admin_id: int):
        """Ресторанға Admin тағайындау"""
        restaurant = db.query(Restaurant).filter(
            Restaurant.id == restaurant_id,
            Restaurant.owner_id == owner_id
        ).first()

        if not restaurant:
            raise HTTPException(status_code=404, detail="Ресторан табылмады")

        admin = db.query(User).filter(
            User.id == admin_id,
            User.role == UserRole.ADMIN
        ).first()

        if not admin:
            raise HTTPException(status_code=404, detail="Admin табылмады")

        restaurant.admin_id = admin_id
        admin.restaurant_id = restaurant.id
        db.commit()
        db.refresh(restaurant)
        return restaurant
