# ── STAGE 1: DATABASE SETUP ───────────────────────────────────────────────────
# File: database.py

from sqlalchemy import (create_engine, Column, Integer, Float,
                        String, DateTime, Boolean, Text, ForeignKey)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

# ── 1a. Engine & Base ─────────────────────────────────────────────────────────
DATABASE_URL = "sqlite:///./maize_platform.db"
engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base         = declarative_base()

# ── 1b. Farmers Table ─────────────────────────────────────────────────────────
class Farmer(Base):
    __tablename__ = "farmers"

    id                    = Column(Integer, primary_key=True, index=True)
    full_name             = Column(String, nullable=False)
    phone_number          = Column(String, unique=True, nullable=False)  # WhatsApp number
    province              = Column(String, nullable=False)
    farming_scale         = Column(String, nullable=False)
    area_cultivated_ha    = Column(Float,  nullable=False)
    agro_ecological_zone  = Column(String, nullable=False)
    soil_type             = Column(String, nullable=False)
    maize_variety         = Column(String, nullable=False)
    registered_at         = Column(DateTime, default=datetime.utcnow)
    is_active             = Column(Boolean, default=True)

    predictions = relationship("Prediction", back_populates="farmer")
    matches     = relationship("Match",      back_populates="farmer")

# ── 1c. Buyers Table ──────────────────────────────────────────────────────────
class Buyer(Base):
    __tablename__ = "buyers"

    id               = Column(Integer, primary_key=True, index=True)
    full_name        = Column(String, nullable=False)
    phone_number     = Column(String, unique=True, nullable=False)
    company_name     = Column(String, nullable=True)
    province         = Column(String, nullable=False)
    quantity_needed  = Column(Float,  nullable=False)   # kg
    price_offered    = Column(Float,  nullable=False)   # USD per kg
    registered_at    = Column(DateTime, default=datetime.utcnow)
    is_active        = Column(Boolean, default=True)

    matches = relationship("Match", back_populates="buyer")

# ── 1d. Predictions Table ─────────────────────────────────────────────────────
class Prediction(Base):
    __tablename__ = "predictions"

    id                       = Column(Integer, primary_key=True, index=True)
    farmer_id                = Column(Integer, ForeignKey("farmers.id"))
    seasonal_rainfall_mm     = Column(Float,  nullable=False)
    fertilizer_kg_ha         = Column(Float,  nullable=False)
    irrigation               = Column(Integer, nullable=False)   # 0 or 1
    improved_seed            = Column(Integer, nullable=False)   # 0 or 1
    pesticide_used           = Column(Integer, nullable=False)   # 0 or 1
    planting_date_delay_days = Column(Integer, nullable=False)
    predicted_yield_kg_ha    = Column(Float,  nullable=False)
    total_yield_kg           = Column(Float,  nullable=False)    # yield × area
    predicted_at             = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("Farmer", back_populates="predictions")

# ── 1e. Matches Table ─────────────────────────────────────────────────────────
class Match(Base):
    __tablename__ = "matches"

    id            = Column(Integer, primary_key=True, index=True)
    farmer_id     = Column(Integer, ForeignKey("farmers.id"))
    buyer_id      = Column(Integer, ForeignKey("buyers.id"))
    quantity_kg   = Column(Float,  nullable=False)
    price_per_kg  = Column(Float,  nullable=False)
    total_value   = Column(Float,  nullable=False)   # quantity × price
    status        = Column(String, default="pending")  # pending/accepted/rejected
    matched_at    = Column(DateTime, default=datetime.utcnow)
    notified      = Column(Boolean, default=False)    # WhatsApp notification sent

    farmer = relationship("Farmer", back_populates="matches")
    buyer  = relationship("Buyer",  back_populates="matches")

# ── 1f. Market Prices Table ───────────────────────────────────────────────────
class MarketPrice(Base):
    __tablename__ = "market_prices"

    id           = Column(Integer, primary_key=True, index=True)
    province     = Column(String, nullable=False)
    price_usd_kg = Column(Float,  nullable=False)
    price_usd_t  = Column(Float,  nullable=False)   # per tonne
    recorded_at  = Column(DateTime, default=datetime.utcnow)
    source       = Column(String, default="Manual Entry")

# ── 1g. Create all tables ─────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialised — all tables created.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── 1h. Seed initial market prices ───────────────────────────────────────────
def seed_market_prices():
    db = SessionLocal()
    existing = db.query(MarketPrice).first()
    if not existing:
        prices = [
            MarketPrice(province="Mashonaland West",    price_usd_kg=0.28, price_usd_t=280),
            MarketPrice(province="Mashonaland East",    price_usd_kg=0.27, price_usd_t=270),
            MarketPrice(province="Mashonaland Central", price_usd_kg=0.27, price_usd_t=270),
            MarketPrice(province="Manicaland",          price_usd_kg=0.26, price_usd_t=260),
            MarketPrice(province="Masvingo",            price_usd_kg=0.29, price_usd_t=290),
            MarketPrice(province="Midlands",            price_usd_kg=0.28, price_usd_t=280),
            MarketPrice(province="Matabeleland North",  price_usd_kg=0.30, price_usd_t=300),
            MarketPrice(province="Matabeleland South",  price_usd_kg=0.31, price_usd_t=310),
        ]
        db.add_all(prices)
        db.commit()
        print("Market prices seeded.")
    db.close()

if __name__ == "__main__":
    init_db()
    seed_market_prices()
    print("Run: python database.py to initialise.")