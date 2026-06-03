from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import joblib
import pandas as pd
from datetime import date, timedelta

app = FastAPI(title="Crop Yield & Buyer Matching API")

# Load trained model
model = joblib.load("crop_yield_catboost_model.pkl")

# Mock buyer registry (replace with DB in production)
BUYERS = [
    {"name": "AgriTrade Pvt Ltd", "crop": "Maize", "location": "Guntur", "price": 28, "phone": "+919999999001"},
    {"name": "Fresh Foods Co", "crop": "Soyabeans", "location": "Vijayawada", "price": 42, "phone": "+919999999002"},
    {"name": "Cotton Mills Ltd", "crop": "Cotton", "location": "Hyderabad", "price": 61, "phone": "+919999999003"},
]

class PredictionInput(BaseModel):
    Region: str
    Soil_Type: str
    Crop: str
    Rainfall_mm: float
    Temperature_Celsius: float
    Fertilizer_Used: bool
    Irrigation_Used: bool
    Weather_Condition: str
    Days_to_Harvest: int
    location: str

@app.get("/")
def root():
    return {"message": "Crop Yield & Buyer Matching API is running"}

@app.post("/predict")
def predict(payload: PredictionInput):
    input_df = pd.DataFrame([payload.dict()])

    predicted_yield = float(model.predict(input_df)[0])
    suggested_price = round(predicted_yield * 5.5, 2)
    harvest_date = str(date.today() + timedelta(days=payload.Days_to_Harvest))

    matched_buyers = [
        buyer for buyer in BUYERS
        if buyer["crop"].lower() == payload.Crop.lower()
    ]

    whatsapp_message = (
        f"Hello, I have {predicted_yield:.2f} tons of {payload.Crop} "
        f"available from {payload.location} for harvest on {harvest_date} "
        f"at an indicative price of ₹{suggested_price}/kg. Are you interested?"
    )

    return {
        "predicted_yield": predicted_yield,
        "suggested_price": suggested_price,
        "harvest_date": harvest_date,
        "buyers": matched_buyers,
        "whatsapp_offer": whatsapp_message
    }

@app.get("/buyers/{crop}")
def get_buyers(crop: str):
    return [buyer for buyer in BUYERS if buyer["crop"].lower() == crop.lower()]
