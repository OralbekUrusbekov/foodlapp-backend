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
from config import settings
import json
from google import genai

client = None
if settings.GEMINI_API_KEY:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

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
    
    # Simple Mock Generation Logic as Fallback
    def generate_mock():
        return [
            {"type": "Таңғы ас", "food": "Сұлы ботқасы бананмен", "kcal": 350, "p": 12, "f": 8, "c": 55, "id": None},
            {"type": "Түскі ас", "food": "Тауық еті мен күріш", "kcal": 650, "p": 45, "f": 15, "c": 75, "id": None},
            {"type": "Кешкі ас", "food": "Балық пен көкөністер", "kcal": 450, "p": 35, "f": 12, "c": 20, "id": None},
        ]
        
    meals_data = None
    
    if settings.GEMINI_API_KEY:
        from app.models.food import Food
        # Get available subscription foods to recommend
        available_foods = db.query(Food).all()
        foods_text = "\n".join([f"- ID: {f.id}, Тағам: {f.name}, {f.calories} ккал" for f in available_foods])
        
        prompt = f"""
        Сен кәсіби диетологсың. Пайдаланушы мәліметтері:
        Жасы: {profile.age}, Жынысы: {profile.gender}, Бойы: {profile.height} см, Салмағы: {profile.weight} кг.
        Мақсаттары: {profile.goal}
        Қозғалыс деңгейі: {profile.activity_level}
        Диета: {profile.diet_type}
        Аллергия: {profile.allergies or "Жоқ"}
        Ұнатпайтін тағамдары: {profile.dislikes or "Жоқ"}
        
        Төменде мәзірде бар тағамдар тізімі берілген:
        {foods_text}
        
        Осы тізімнен пайдаланушыға сәйкес келетін 1 күндік рацион (Таңғы ас, Түскі ас, Кешкі ас) құрастыр. 
        Тек JSON массив форматында қайтар (ешқандай қосымша мәтінсіз, Markdown форматтаусыз). 
        Мысал:
        [
            {{"type": "Таңғы ас", "food": "Тағам аты", "id": 1, "kcal": 300, "p": 15, "f": 10, "c": 35}},
            {{"type": "Түскі ас", "food": "Тағам аты", "id": 2, "kcal": 500, "p": 30, "f": 15, "c": 50}},
            {{"type": "Кешкі ас", "food": "Басқа тағам", "id": 3, "kcal": 400, "p": 25, "f": 12, "c": 30}}
        ]
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            # Clean response text in case of backticks
            response_text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
            meals_data = json.loads(response_text)
        except Exception as e:
            print(f"Gemini generation error: {e}")
            meals_data = generate_mock()
    else:
        meals_data = generate_mock()
    
    new_rations = []
    for m in meals_data:
        ration = Ration(
            user_id=current_user.id,
            date=today,
            meal_type=m.get("type", "Ас"),
            food_name=m.get("food", ""),
            calories=m.get("kcal", 0),
            proteins=m.get("p", 0),
            fats=m.get("f", 0),
            carbs=m.get("c", 0),
            is_orderable=bool(m.get("id")),
            food_id=m.get("id")
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
    db = next(get_db())
    profile = db.query(AIProfile).filter(AIProfile.user_id == current_user.id).first()
    
    if client:
        try:
            context = f"Сен FoodLapp қосымшасының AI диетологысың. Қысқаша, достық әрі пайдалы жауап бер."
            if profile:
                context += f"\nПайдаланушы мәліметтері: Жасы: {profile.age}, Салмағы: {profile.weight}кг, Мақсаты: {profile.goal}, Диетасы: {profile.diet_type}."
            
            prompt = f"{context}\nСұрақ: {message.message}"
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return ChatResponse(reply=response.text)
        except Exception as e:
            print(f"Gemini chat error: {e}")
            return ChatResponse(reply="Кешіріңіз, қазіргі уақытта жауап бере алмаймын. Байланыс ақауы.")
            
    # Fallback to mock
    msg = message.message.lower()
    if "арықтау" in msg:
        reply = "Арықтау үшін тәуліктік калория мөлшерін азайтып, ақуызды көбейту керек. Күніне кемінде 2 литр су ішіңіз."
    elif "салмақ қосу" in msg:
        reply = "Салмақ қосу үшін күрделі көмірсулар мен пайдалы майларды көбірек тұтыныңыз. Күштік жаттығулар жасаған дұрыс."
    else:
        reply = f"Сәлем, {current_user.full_name}! Мен сіздің AI диетологыңызбын. (API кілті орнатылмағандықтан, жауаптар шектеулі)"
    
    return ChatResponse(reply=reply)
