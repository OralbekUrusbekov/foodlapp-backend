import sys
import os
sys.path.append(os.getcwd())
import traceback

try:
    from app.database.connection import SessionLocal
    from app.models.user import User, UserRole
    from app.api.cashier import get_active_orders
    from fastapi.encoders import jsonable_encoder

    db = SessionLocal()
    cashier = db.query(User).filter(User.role == UserRole.CASHIER).first()
    if not cashier:
        print("No cashier")
        sys.exit()

    orders = get_active_orders(db, cashier)
    print("Orders retrieved:", len(orders))
    
    enc = jsonable_encoder(orders)
    print("Serialization success:", len(enc))

except Exception as e:
    with open("error_log.utf8.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
