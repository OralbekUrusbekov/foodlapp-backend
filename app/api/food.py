from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.FoodImage import FoodImage
from app.models.food import Food, MenuType
from app.models.user import User
from app.configuration.security.dependencies import get_canteen_admin_user, get_owner_user
from app.utils.s3_upload import upload_file_to_s3

router = APIRouter()

from typing import List
from fastapi import UploadFile, File, Form

@router.post("/foods", status_code=201)
def create_food(
    name: str = Form(...),
    description: str = Form(None),
    calories: int = Form(None),
    ingredients: str = Form(None),
    is_available: bool = Form(True),
    images: List[UploadFile] = File(...),

    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    # Тек Owner қоса алады, branch_id қажет емес немесе басқаша өңделеді
    # Бірақ бұл жерде бұрынғы логика бойынша branch_id қолданылып келген.
    # User сұрауы бойынша "Тек қана овнер абономентке арналған мәзерді қоса алады"
    # Сондықтан бұл жерде branch_id тексерісін алып тастаймыз немесе Owner-ге сәйкестендіреміз.
    
    # 📌 Food create
    new_food = Food(
        name=name,
        description=description,
        calories=calories,
        ingredients=ingredients,
        menu_type=MenuType.SUBSCRIPTION, # Always subscription
        owner_id=current_user.id
    )

    db.add(new_food)
    db.commit()
    db.refresh(new_food)

    # 📌 Upload images → S3 → DB
    for image in images:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Тек сурет жіберіңіз")

        image_url = upload_file_to_s3(image, image.content_type)

        food_image = (
            FoodImage(
            image_url=image_url,
            food_id=new_food.id
        ))

        db.add(food_image)

    db.commit()

    return new_food


@router.get("/foods/{food_id}")
def get_food(food_id: int, db: Session = Depends(get_db)):
    food = db.query(Food).filter(Food.id == food_id).first()

    if not food:
        raise HTTPException(status_code=404, detail="Тағам табылмады")

    return food



@router.put("/foods/{food_id}/images")
def add_food_images(
    food_id: int,
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    food = db.query(Food).filter(Food.id == food_id).first()

    if not food:
        raise HTTPException(status_code=404, detail="Тағам табылмады")

    for image in images:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Тек сурет жіберіңіз")

        image_url = upload_file_to_s3(image, image.content_type)

        db.add(FoodImage(image_url=image_url, food_id=food.id))

    db.commit()

    return {"message": "Суреттер қосылды"}


