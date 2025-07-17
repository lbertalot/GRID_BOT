import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.db.session import engine, Base
from app.models.grid_config import GridConfig

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db() 