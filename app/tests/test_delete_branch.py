import sys
import os
sys.path.append(os.getcwd())
import traceback

try:
    from app.database.connection import SessionLocal
    from app.models.branch import Branch

    db = SessionLocal()
    # Find any branch
    branch = db.query(Branch).first()
    if branch:
        print(f"Trying to delete branch {branch.id}")
        db.delete(branch)
        db.commit()
    else:
        print("No branches found.")
except Exception as e:
    with open("error_log.utf8.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print("Error written to error_log.utf8.txt")
