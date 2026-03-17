from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app.database.connection import get_db
from app.configuration.security.dependencies import get_current_active_user
from app.models.user import User
from app.models.ai_profile import AIProfile
from app.models.weight_history import WeightHistory
from app.models.ration import Ration
from app.schemas.ai_dto import (
    AIProfileDTO, AIProfileUpdate, WeightEntryCreate, 
    WeightHistoryDTO, RationDTO, ChatMessage, ChatResponse
)

router = APIRouter()

@router.get("/profile", response_model=AIProfileDTO)
def get_ai_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    profile = db.query(AIProfile).filter(AIProfile.user_id == current_user.id).first()
    if not profile:
        # Create an empty profile if it doesn't exist
        profile = AIProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

@router.post("/profile", response_model=AIProfileDTO)
def update_ai_profile(
    profile_data: AIProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    profile = db.query(AIProfile).filter(AIProfile.user_id == current_user.id).first()
    if not profile:
        profile = AIProfile(user_id=current_user.id)
        db.add(profile)
    
    for field, value in profile_data.dict(exclude_unset=True).items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile

@router.post("/weight", response_model=WeightHistoryDTO)
def log_weight(
    entry: WeightEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    weight_entry = WeightHistory(user_id=current_user.id, weight=entry.weight)
    db.add(weight_entry)
    
    # Also update current weight in profile
    profile = db.query(AIProfile).filter(AIProfile.user_id == current_user.id).first()
    if profile:
        profile.weight = entry.weight
    
    db.commit()
    db.refresh(weight_entry)
    return weight_entry

@router.get("/weight-history", response_model=List[WeightHistoryDTO])
def get_weight_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return db.query(WeightHistory).filter(WeightHistory.user_id == current_user.id).order_by(WeightHistory.date.desc()).all()

@router.post("/generate-ration", response_model=List[RationDTO])
def generate_ration(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    profile = db.query(AIProfile).filter(AIProfile.user_id == current_user.id).first()
    if not profile or not profile.weight or not profile.height:
        raise HTTPException(status_code=400, detail="Алдымен профильді толтырыңыз (салмақ, бой)")
    
    # Simple Mock Generation Logic
    # In a real app, this would call an AI service or use a sophisticated nutrition algorithm
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Check if ration for today already exists
    existing = db.query(Ration).filter(Ration.user_id == current_user.id, Ration.date >= today).all()
    if existing:
        return existing
    
    # Generate mock ration for 1 day
    meals = [
        {"type": "Таңғы ас", "food": "Сұлы ботқасы бананмен", "kcal": 350, "p": 12, "f": 8, "c": 55},
        {"type": "Түскі ас", "food": "Тауық еті мен күріш", "kcal": 650, "p": 45, "f": 15, "c": 75},
        {"type": "Кешкі ас", "food": "Балық пен көкөністер", "kcal": 450, "p": 35, "f": 12, "c": 20},
    ]
    
    new_rations = []
    for m in meals:
        ration = Ration(
            user_id=current_user.id,
            date=today,
            meal_type=m["type"],
            food_name=m["food"],
            calories=m["kcal"],
            proteins=m["p"],
            fats=m["f"],
            carbs=m["c"],
            is_orderable=True # Mock integration
        )
        db.add(ration)
        new_rations.append(ration)
    
    db.commit()
    for r in new_rations:
        db.refresh(r)
    return new_rations

@router.get("/ration/today", response_model=List[RationDTO])
def get_today_ration(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(Ration).filter(Ration.user_id == current_user.id, Ration.date >= today).all()

@router.post("/chat", response_model=ChatResponse)
def ai_chat(
    message: ChatMessage,
    current_user: User = Depends(get_current_active_user)
):
    # Mock AI response logic
    msg = message.message.lower()
    if "арықтау" in msg:
        reply = "Арықтау үшін тәуліктік калория мөлшерін азайтып, ақуызды көбейту керек. Күніне кемінде 2 литр су ішіңіз."
    elif "салмақ қосу" in msg:
        reply = "Салмақ қосу үшін күрделі көмірсулар мен пайдалы майларды көбірек тұтыныңыз. Күштік жаттығулар жасаған дұрыс."
    else:
        reply = f"Сәлем, {current_user.full_name}! Мен сіздің AI диетологыңызбын. Қалай көмектесе алам? Сіздің қазіргі мақсатыңызға сай ұсыныстар бере аламын."
    
    return ChatResponse(reply=reply)
