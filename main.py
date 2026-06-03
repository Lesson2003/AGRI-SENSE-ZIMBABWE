# ── FULL main.py ──────────────────────────────────────────────────────────────
# File: main.py

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import joblib
import numpy as np
import pandas as pd
from twilio.twiml.messaging_response import MessagingResponse
from whatsapp_bot import handle_message
from database import (get_db, init_db, seed_market_prices,
                      Farmer, Buyer, Prediction, Match, MarketPrice)

app = FastAPI(title="Zimbabwe Maize Yield Platform", version="1.0")

# ── Load ML Model ─────────────────────────────────────────────────────────────
model = joblib.load("zimbabwe_maize_yield_tuned.pkl")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    seed_market_prices()
    print("App started — database ready.")

# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class FarmerCreate(BaseModel):
    full_name            : str
    phone_number         : str
    province             : str
    farming_scale        : str
    area_cultivated_ha   : float
    agro_ecological_zone : str
    soil_type            : str
    maize_variety        : str

class BuyerCreate(BaseModel):
    full_name       : str
    phone_number    : str
    company_name    : Optional[str] = None
    province        : str
    quantity_needed : float
    price_offered   : float

class PredictionRequest(BaseModel):
    farmer_id                : int
    seasonal_rainfall_mm     : float
    fertilizer_kg_ha         : float
    irrigation               : int
    improved_seed            : int
    pesticide_used           : int
    planting_date_delay_days : int

class MarketPriceUpdate(BaseModel):
    province     : str
    price_usd_kg : float
    source       : Optional[str] = "Manual Entry"

# ── Validation Lists ──────────────────────────────────────────────────────────
VALID_PROVINCES = [
    "Mashonaland West", "Mashonaland East", "Mashonaland Central",
    "Manicaland", "Masvingo", "Midlands",
    "Matabeleland North", "Matabeleland South"
]
VALID_SCALES  = ["Smallholder", "Small Commercial", "Large Commercial"]
VALID_AEZ     = ["I", "II", "IIb", "III", "IV", "V"]
VALID_SOILS   = ["Sandy Loam", "Clay Loam", "Sandy", "Red Clay"]
VALID_VARIETY = ["SC403", "SC513", "ZM421", "ZM521", "DKC80-73", "Local/OPV"]

# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "running", "platform": "Zimbabwe Maize Yield Platform"}

# ── Farmer Endpoints ──────────────────────────────────────────────────────────
@app.post("/farmers/register")
def register_farmer(data: FarmerCreate, db: Session = Depends(get_db)):

    # Validate inputs
    if data.province not in VALID_PROVINCES:
        raise HTTPException(status_code=400,
                            detail=f"Invalid province: {data.province}")
    if data.farming_scale not in VALID_SCALES:
        raise HTTPException(status_code=400,
                            detail=f"Invalid farming scale: {data.farming_scale}")
    if data.agro_ecological_zone not in VALID_AEZ:
        raise HTTPException(status_code=400,
                            detail=f"Invalid AEZ: {data.agro_ecological_zone}")
    if data.soil_type not in VALID_SOILS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid soil type: {data.soil_type}")
    if data.maize_variety not in VALID_VARIETY:
        raise HTTPException(status_code=400,
                            detail=f"Invalid maize variety: {data.maize_variety}")
    if data.area_cultivated_ha <= 0:
        raise HTTPException(status_code=400,
                            detail="Area must be greater than 0.")
    if not data.full_name.strip():
        raise HTTPException(status_code=400,
                            detail="Full name cannot be empty.")
    if not data.phone_number.strip():
        raise HTTPException(status_code=400,
                            detail="Phone number cannot be empty.")

    # Check duplicate
    existing = db.query(Farmer).filter(
        Farmer.phone_number == data.phone_number
    ).first()
    if existing:
        raise HTTPException(status_code=400,
                            detail="Phone number already registered.")

    farmer = Farmer(**data.dict())
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return {"message": "Farmer registered successfully.", "farmer_id": farmer.id}

@app.get("/farmers")
def get_all_farmers(db: Session = Depends(get_db)):
    farmers = db.query(Farmer).filter(Farmer.is_active == True).all()
    return {"total": len(farmers), "farmers": [
        {
            "id"      : f.id,
            "name"    : f.full_name,
            "phone"   : f.phone_number,
            "province": f.province,
            "scale"   : f.farming_scale,
            "area_ha" : f.area_cultivated_ha,
            "aez"     : f.agro_ecological_zone,
            "soil"    : f.soil_type,
            "variety" : f.maize_variety,
        } for f in farmers
    ]}

@app.get("/farmers/{farmer_id}")
def get_farmer(farmer_id: int, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found.")
    return {
        "id"                  : farmer.id,
        "full_name"           : farmer.full_name,
        "phone_number"        : farmer.phone_number,
        "province"            : farmer.province,
        "farming_scale"       : farmer.farming_scale,
        "area_cultivated_ha"  : farmer.area_cultivated_ha,
        "agro_ecological_zone": farmer.agro_ecological_zone,
        "soil_type"           : farmer.soil_type,
        "maize_variety"       : farmer.maize_variety,
        "registered_at"       : farmer.registered_at,
        "is_active"           : farmer.is_active,
    }

@app.delete("/farmers/{farmer_id}")
def deactivate_farmer(farmer_id: int, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found.")
    farmer.is_active = False
    db.commit()
    return {"message": f"Farmer {farmer.full_name} deactivated."}

# ── Buyer Endpoints ───────────────────────────────────────────────────────────
@app.post("/buyers/register")
def register_buyer(data: BuyerCreate, db: Session = Depends(get_db)):

    # Validate inputs
    if data.province not in VALID_PROVINCES:
        raise HTTPException(status_code=400,
                            detail=f"Invalid province: {data.province}")
    if data.quantity_needed <= 0:
        raise HTTPException(status_code=400,
                            detail="Quantity must be greater than 0.")
    if data.price_offered <= 0:
        raise HTTPException(status_code=400,
                            detail="Price must be greater than 0.")
    if not data.full_name.strip():
        raise HTTPException(status_code=400,
                            detail="Full name cannot be empty.")
    if not data.phone_number.strip():
        raise HTTPException(status_code=400,
                            detail="Phone number cannot be empty.")

    # Check duplicate
    existing = db.query(Buyer).filter(
        Buyer.phone_number == data.phone_number
    ).first()
    if existing:
        raise HTTPException(status_code=400,
                            detail="Phone number already registered.")

    buyer = Buyer(**data.dict())
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return {"message": "Buyer registered successfully.", "buyer_id": buyer.id}

@app.get("/buyers")
def get_all_buyers(db: Session = Depends(get_db)):
    buyers = db.query(Buyer).filter(Buyer.is_active == True).all()
    return {"total": len(buyers), "buyers": [
        {
            "id"                  : b.id,
            "name"                : b.full_name,
            "company"             : b.company_name,
            "phone"               : b.phone_number,
            "province"            : b.province,
            "quantity_needed_kg"  : b.quantity_needed,
            "price_offered_usd_kg": b.price_offered,
        } for b in buyers
    ]}

# ── Prediction Endpoint ───────────────────────────────────────────────────────
@app.post("/predict")
def predict_yield(data: PredictionRequest, db: Session = Depends(get_db)):

    # Validate inputs
    if data.seasonal_rainfall_mm < 0:
        raise HTTPException(status_code=400,
                            detail="Rainfall cannot be negative.")
    if data.fertilizer_kg_ha < 0:
        raise HTTPException(status_code=400,
                            detail="Fertilizer cannot be negative.")
    if data.irrigation not in [0, 1]:
        raise HTTPException(status_code=400,
                            detail="Irrigation must be 0 or 1.")
    if data.improved_seed not in [0, 1]:
        raise HTTPException(status_code=400,
                            detail="Improved seed must be 0 or 1.")
    if data.pesticide_used not in [0, 1]:
        raise HTTPException(status_code=400,
                            detail="Pesticide used must be 0 or 1.")
    if data.planting_date_delay_days < 0:
        raise HTTPException(status_code=400,
                            detail="Planting delay cannot be negative.")

    # Fetch farmer
    farmer = db.query(Farmer).filter(Farmer.id == data.farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found.")

    # AEZ ordinal mapping
    aez_map = {'I': 5, 'II': 4, 'IIb': 3, 'III': 3, 'IV': 2, 'V': 1}

    # Build input dataframe
    input_df = pd.DataFrame([{
        'Seasonal Rainfall mm'     : data.seasonal_rainfall_mm,
        'Area Cultivated ha'       : farmer.area_cultivated_ha,
        'Farming Scale'            : farmer.farming_scale,
        'AEZ_Ordinal'              : aez_map.get(farmer.agro_ecological_zone, 3),
        'Improved Seed'            : data.improved_seed,
        'Fertilizer kg ha'         : data.fertilizer_kg_ha,
        'Irrigation'               : data.irrigation,
        'Planting Date Delay days' : data.planting_date_delay_days,
        'Province'                 : farmer.province,
        'Pesticide Used'           : data.pesticide_used,
    }])

    # Predict
    log_pred       = model.predict(input_df)[0]
    yield_kg_ha    = round(np.expm1(log_pred), 2)
    total_yield_kg = round(yield_kg_ha * farmer.area_cultivated_ha, 2)
    total_yield_t  = round(total_yield_kg / 1000, 3)

    # Get market price
    market = (db.query(MarketPrice)
                .filter(MarketPrice.province == farmer.province)
                .order_by(MarketPrice.recorded_at.desc())
                .first())
    price_usd_kg = market.price_usd_kg if market else 0.28
    est_revenue  = round(total_yield_kg * price_usd_kg, 2)

    # Save prediction
    pred = Prediction(
        farmer_id                = farmer.id,
        seasonal_rainfall_mm     = data.seasonal_rainfall_mm,
        fertilizer_kg_ha         = data.fertilizer_kg_ha,
        irrigation               = data.irrigation,
        improved_seed            = data.improved_seed,
        pesticide_used           = data.pesticide_used,
        planting_date_delay_days = data.planting_date_delay_days,
        predicted_yield_kg_ha    = yield_kg_ha,
        total_yield_kg           = total_yield_kg,
    )
    db.add(pred)
    db.commit()

    return {
        "farmer"               : farmer.full_name,
        "province"             : farmer.province,
        "area_ha"              : farmer.area_cultivated_ha,
        "predicted_yield_kg_ha": yield_kg_ha,
        "total_yield_kg"       : total_yield_kg,
        "total_yield_tonnes"   : total_yield_t,
        "market_price_usd_kg"  : price_usd_kg,
        "estimated_revenue_usd": est_revenue,
    }

# ── Matching Endpoint ─────────────────────────────────────────────────────────
@app.post("/match/{farmer_id}")
def match_farmer_to_buyers(farmer_id: int, db: Session = Depends(get_db)):

    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found.")

    # Get latest prediction
    latest_pred = (db.query(Prediction)
                     .filter(Prediction.farmer_id == farmer_id)
                     .order_by(Prediction.predicted_at.desc())
                     .first())
    if not latest_pred:
        raise HTTPException(status_code=400,
                            detail="No prediction found. Run /predict first.")

    # Find matching buyers
    buyers = (db.query(Buyer)
                .filter(Buyer.is_active == True)
                .filter(Buyer.quantity_needed <= latest_pred.total_yield_kg)
                .order_by(Buyer.price_offered.desc())
                .all())

    if not buyers:
        return {"message": "No matching buyers found at this time."}

    matches_created = []
    for buyer in buyers[:3]:
        total_value = round(buyer.quantity_needed * buyer.price_offered, 2)
        match = Match(
            farmer_id    = farmer_id,
            buyer_id     = buyer.id,
            quantity_kg  = buyer.quantity_needed,
            price_per_kg = buyer.price_offered,
            total_value  = total_value,
            status       = "pending",
            notified     = False,
        )
        db.add(match)
        matches_created.append({
            "buyer"          : buyer.full_name,
            "company"        : buyer.company_name,
            "quantity_kg"    : buyer.quantity_needed,
            "price_usd_kg"   : buyer.price_offered,
            "total_value_usd": total_value,
            "buyer_phone"    : buyer.phone_number,
        })

    db.commit()
    return {
        "farmer" : farmer.full_name,
        "matches": matches_created,
        "message": f"{len(matches_created)} buyer(s) matched successfully."
    }

# ── Market Price Endpoints ────────────────────────────────────────────────────
@app.get("/prices")
def get_prices(db: Session = Depends(get_db)):
    prices = db.query(MarketPrice).order_by(
        MarketPrice.recorded_at.desc()
    ).all()
    return {"prices": [
        {
            "province"    : p.province,
            "price_usd_kg": p.price_usd_kg,
            "price_usd_t" : p.price_usd_t,
            "recorded_at" : p.recorded_at,
            "source"      : p.source
        } for p in prices
    ]}

@app.post("/prices/update")
def update_price(data: MarketPriceUpdate, db: Session = Depends(get_db)):
    if data.province not in VALID_PROVINCES:
        raise HTTPException(status_code=400,
                            detail=f"Invalid province: {data.province}")
    if data.price_usd_kg <= 0:
        raise HTTPException(status_code=400,
                            detail="Price must be greater than 0.")
    price = MarketPrice(
        province     = data.province,
        price_usd_kg = data.price_usd_kg,
        price_usd_t  = round(data.price_usd_kg * 1000, 2),
        source       = data.source,
    )
    db.add(price)
    db.commit()
    return {"message": f"Price updated for {data.province} — ${data.price_usd_kg}/kg"}

@app.patch("/matches/{match_id}")
def update_match_status(match_id: int, status: str,
                         db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if status not in ["pending", "accepted", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status.")
    match.status = status
    db.commit()
    return {"message": f"Match {match_id} updated to '{status}'."}

# ── WhatsApp Webhook ──────────────────────────────────────────────────────────
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        form   = await request.form()
        msg    = form.get("Body", "")
        sender = form.get("From", "").replace("whatsapp:", "")

        print(f"WhatsApp — From: {sender} | Message: {msg}")

        reply  = handle_message(sender, msg)
        resp   = MessagingResponse()
        resp.message(reply)
        return Response(content=str(resp), media_type="application/xml")

    except Exception as e:
        import traceback
        print("WEBHOOK ERROR:", traceback.format_exc())
        return Response(content="Error", status_code=500)

# ── Run: uvicorn main:app --reload ────────────────────────────────────────────