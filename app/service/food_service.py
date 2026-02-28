from sqlalchemy.orm import Session
from app.models.food import Food
from fastapi import HTTPException, status

class FoodService:
    
    @staticmethod
    def get_foods_by_branch(db: Session, branch_id: int):
        """Филиал бойынша тағамдарды алу"""
        return db.query(Food).filter(
            Food.branch_id == branch_id,
            Food.is_available == True
        ).all()
    
    @staticmethod
    def create_food(db: Session, food_data: dict) -> Food:
        """Жаңа тағам қосу"""
        new_food = Food(**food_data)
        db.add(new_food)
        db.commit()
        db.refresh(new_food)
        return new_food
    
    @staticmethod
    def update_food(db: Session, food_id: int, update_data: dict) -> Food:
        """Тағамды жаңарту"""
        food = db.query(Food).filter(Food.id == food_id).first()
        
        if not food:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Тағам табылмады"
            )
        
        for key, value in update_data.items():
            if value is not None:
                setattr(food, key, value)
        
        db.commit()
        db.refresh(food)
        return food
    
    @staticmethod
    def delete_food(db: Session, food_id: int):
        """Тағамды өшіру"""
        food = db.query(Food).filter(Food.id == food_id).first()
        
        if not food:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Тағам табылмады"
            )
        
        db.delete(food)
        db.commit()
        return {"message": "Тағам өшірілді"}
