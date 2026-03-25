import sys
import os
import psycopg2

env_path = os.path.join(os.getcwd(), ".env")
env_vars = {}
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'").strip('"')

conn = psycopg2.connect(
    dbname=env_vars.get("POSTGRES_DB", "foodlab_db"),
    user=env_vars.get("POSTGRES_USER", "postgres"),
    password=env_vars.get("POSTGRES_PASSWORD", "postgres"),
    host=env_vars.get("POSTGRES_SERVER", "localhost"),
    port=env_vars.get("POSTGRES_PORT", 5432)
)
conn.autocommit = True

with conn.cursor() as cur:
    print("Checking enum values...")
    cur.execute("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'orderstatus';")
    labels = [row[0] for row in cur.fetchall()]
    print(f"Current labels: {labels}")
    
    needed = ['pending', 'accepted', 'cooking', 'ready', 'given', 'cancelled']
    for val in needed:
        if val not in labels:
            print(f"Adding '{val}' to orderstatus")
            try:
                cur.execute(f"ALTER TYPE orderstatus ADD VALUE '{val}';")
            except Exception as e:
                print(f"Failed to add {val}: {e}")
