import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'pipeline.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from database.models import Property
    Base.metadata.create_all(bind=engine)
    columns = {
        "floors": "INTEGER",
        "unit_number": "VARCHAR",
        "total_units": "INTEGER",
        "showing_instructions": "TEXT",
        "garage_spaces": "INTEGER",
        "pet_types_allowed": "TEXT",
        "pet_weight_limit": "INTEGER",
        "minimum_lease_months": "INTEGER",
        "security_deposit": "INTEGER",
        "last_months_rent": "INTEGER",
        "application_fee": "INTEGER",
        "pet_deposit": "INTEGER",
        "admin_fee": "INTEGER",
        "move_in_special": "TEXT",
        "parking_fee": "INTEGER",
        "total_bathrooms": "FLOAT",
        "has_basement": "BOOLEAN",
        "has_central_air": "BOOLEAN",
        "data_quality_score": "INTEGER",
        "missing_fields": "TEXT DEFAULT '[]'",
        "inferred_features": "TEXT DEFAULT '[]'",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(properties)"))}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE properties ADD COLUMN {name} {sql_type}"))
