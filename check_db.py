import sys
import os
sys.path.insert(0, os.getcwd())
from utils.config import get_cloud_engine
from sqlalchemy import text
engine = get_cloud_engine()
with engine.connect() as conn:
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'cash_sessions'")).fetchall()
    print([r[0] for r in res])
