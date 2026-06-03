# ── FIXED whatsapp_bot.py ─────────────────────────────────────────────────────
# File: whatsapp_bot.py

from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import numpy as np
import pandas as pd
import joblib
import json
import os
from datetime import datetime
from database import (SessionLocal, Farmer, Buyer,
                      Prediction, Match, MarketPrice)

# ── Twilio Credentials ────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = "your_account_sid_here"
TWILIO_AUTH_TOKEN  = "your_auth_token_here"
TWILIO_WHATSAPP_NO = "whatsapp:+14155238886"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ── Load ML Model ─────────────────────────────────────────────────────────────
model = joblib.load("zimbabwe_maize_yield_tuned.pkl")

# ── AEZ Mapping ───────────────────────────────────────────────────────────────
AEZ_MAP = {'I': 5, 'II': 4, 'IIb': 3, 'III': 3, 'IV': 2, 'V': 1}

# ── Persistent Sessions — saved to file so restarts don't wipe them ───────────
SESSIONS_FILE = "sessions.json"

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sessions(sessions):
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        print(f"Session save error: {e}")

# ── DB Helper Functions — direct DB access, no HTTP ──────────────────────────
def db_register_farmer(data: dict):
    db = SessionLocal()
    try:
        existing = db.query(Farmer).filter(
            Farmer.phone_number == data["phone_number"]
        ).first()
        if existing:
            return None, "Phone number already registered."
        farmer = Farmer(**data)
        db.add(farmer)
        db.commit()
        db.refresh(farmer)
        return farmer.id, None
    except Exception as e:
        db.rollback()
        return None, str(e)
    finally:
        db.close()

def db_register_buyer(data: dict):
    db = SessionLocal()
    try:
        existing = db.query(Buyer).filter(
            Buyer.phone_number == data["phone_number"]
        ).first()
        if existing:
            return None, "Phone number already registered."
        buyer = Buyer(**data)
        db.add(buyer)
        db.commit()
        db.refresh(buyer)
        return buyer.id, None
    except Exception as e:
        db.rollback()
        return None, str(e)
    finally:
        db.close()

def db_get_farmer(farmer_id: int):
    db = SessionLocal()
    try:
        return db.query(Farmer).filter(Farmer.id == farmer_id).first()
    finally:
        db.close()

def db_predict_and_save(farmer_id: int, inputs: dict):
    db = SessionLocal()
    try:
        farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
        if not farmer:
            return None, "Farmer not found."

        input_df = pd.DataFrame([{
            'Seasonal Rainfall mm'     : inputs["seasonal_rainfall_mm"],
            'Area Cultivated ha'       : farmer.area_cultivated_ha,
            'Farming Scale'            : farmer.farming_scale,
            'AEZ_Ordinal'              : AEZ_MAP.get(farmer.agro_ecological_zone, 3),
            'Improved Seed'            : inputs["improved_seed"],
            'Fertilizer kg ha'         : inputs["fertilizer_kg_ha"],
            'Irrigation'               : inputs["irrigation"],
            'Planting Date Delay days' : inputs["planting_date_delay_days"],
            'Province'                 : farmer.province,
            'Pesticide Used'           : inputs["pesticide_used"],
        }])

        log_pred       = model.predict(input_df)[0]
        yield_kg_ha    = round(np.expm1(log_pred), 2)
        total_yield_kg = round(yield_kg_ha * farmer.area_cultivated_ha, 2)
        total_yield_t  = round(total_yield_kg / 1000, 3)

        market = (db.query(MarketPrice)
                    .filter(MarketPrice.province == farmer.province)
                    .order_by(MarketPrice.recorded_at.desc())
                    .first())
        price_usd_kg = market.price_usd_kg if market else 0.28
        est_revenue  = round(total_yield_kg * price_usd_kg, 2)

        pred = Prediction(
            farmer_id                = farmer.id,
            seasonal_rainfall_mm     = inputs["seasonal_rainfall_mm"],
            fertilizer_kg_ha         = inputs["fertilizer_kg_ha"],
            irrigation               = inputs["irrigation"],
            improved_seed            = inputs["improved_seed"],
            pesticide_used           = inputs["pesticide_used"],
            planting_date_delay_days = inputs["planting_date_delay_days"],
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
        }, None

    except Exception as e:
        db.rollback()
        return None, str(e)
    finally:
        db.close()

def db_match_farmer(farmer_id: int):
    db = SessionLocal()
    try:
        farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
        if not farmer:
            return None, "Farmer not found."

        latest_pred = (db.query(Prediction)
                         .filter(Prediction.farmer_id == farmer_id)
                         .order_by(Prediction.predicted_at.desc())
                         .first())
        if not latest_pred:
            return None, "No prediction found. Run prediction first."

        buyers = (db.query(Buyer)
                    .filter(Buyer.is_active == True)
                    .filter(Buyer.quantity_needed <= latest_pred.total_yield_kg)
                    .order_by(Buyer.price_offered.desc())
                    .all())

        if not buyers:
            return [], None

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
                "company"        : buyer.company_name or "Individual",
                "quantity_kg"    : buyer.quantity_needed,
                "price_usd_kg"   : buyer.price_offered,
                "total_value_usd": total_value,
                "buyer_phone"    : buyer.phone_number,
            })
        db.commit()
        return matches_created, None

    except Exception as e:
        db.rollback()
        return None, str(e)
    finally:
        db.close()

def db_get_prices():
    db = SessionLocal()
    try:
        prices = db.query(MarketPrice).order_by(
            MarketPrice.recorded_at.desc()
        ).all()
        seen = {}
        for p in prices:
            if p.province not in seen:
                seen[p.province] = {
                    "province"    : p.province,
                    "price_usd_kg": p.price_usd_kg,
                    "price_usd_t" : p.price_usd_t,
                }
        return list(seen.values())
    finally:
        db.close()

# ── Main Bot Handler ──────────────────────────────────────────────────────────
def handle_message(from_number: str, message: str) -> str:
    sessions = load_sessions()
    msg      = message.strip().lower()
    session  = sessions.get(from_number, {"step": "start", "data": {}})

    def save(step, data=None):
        sessions[from_number] = {
            "step": step,
            "data": data if data is not None else session.get("data", {})
        }
        save_sessions(sessions)

    reply = _process(from_number, msg, message, session, save)
    return reply

def _process(from_number, msg, raw_msg, session, save):

    # ── MENU ─────────────────────────────────────────────────────────────────
    if msg in ["hi","hello","menu","start","0"]:
        save("menu", {})
        return (
            "🌽 *Zimbabwe Maize Yield Platform*\n\n"
            "Welcome! What would you like to do?\n\n"
            "1️⃣  Register as a Farmer\n"
            "2️⃣  Predict my Maize Yield\n"
            "3️⃣  Find Buyers\n"
            "4️⃣  Check Market Prices\n"
            "5️⃣  Register as a Buyer\n\n"
            "Reply with a number (1-5)"
        )

    step = session.get("step","start")
    data = session.get("data", {})

    # ── OPTION 1: REGISTER FARMER ─────────────────────────────────────────────
    if msg == "1" and step == "menu":
        save("reg_name", {})
        return "📝 *Farmer Registration*\n\nPlease enter your *full name*:"

    if step == "reg_name":
        save("reg_province", {"full_name": raw_msg.strip()})
        return (
            "Which *province* are you in?\n\n"
            "1. Mashonaland West\n2. Mashonaland East\n"
            "3. Mashonaland Central\n4. Manicaland\n"
            "5. Masvingo\n6. Midlands\n"
            "7. Matabeleland North\n8. Matabeleland South\n\n"
            "Reply with a number (1-8)"
        )

    if step == "reg_province":
        provinces = {
            "1":"Mashonaland West",  "2":"Mashonaland East",
            "3":"Mashonaland Central","4":"Manicaland",
            "5":"Masvingo",          "6":"Midlands",
            "7":"Matabeleland North", "8":"Matabeleland South"
        }
        if msg not in provinces:
            return "❌ Invalid. Reply with a number between 1 and 8."
        data["province"] = provinces[msg]
        save("reg_scale", data)
        return (
            "What is your *farming scale*?\n\n"
            "1. Smallholder\n"
            "2. Small Commercial\n"
            "3. Large Commercial\n\n"
            "Reply with a number (1-3)"
        )

    if step == "reg_scale":
        scales = {"1":"Smallholder","2":"Small Commercial","3":"Large Commercial"}
        if msg not in scales:
            return "❌ Invalid. Reply with 1, 2 or 3."
        data["farming_scale"] = scales[msg]
        save("reg_area", data)
        return "How many *hectares* do you cultivate?\n\nExample: 2.5"

    if step == "reg_area":
        try:
            data["area_cultivated_ha"] = float(raw_msg.strip())
        except:
            return "❌ Invalid. Enter a number. Example: 2.5"
        save("reg_aez", data)
        return (
            "What is your *Agro-Ecological Zone*?\n\n"
            "1. AEZ I   (High rainfall)\n"
            "2. AEZ II  (Good rainfall)\n"
            "3. AEZ IIb (Moderate)\n"
            "4. AEZ III (Marginal)\n"
            "5. AEZ IV  (Low rainfall)\n"
            "6. AEZ V   (Very dry)\n\n"
            "Reply with a number (1-6)"
        )

    if step == "reg_aez":
        aez = {"1":"I","2":"II","3":"IIb","4":"III","5":"IV","6":"V"}
        if msg not in aez:
            return "❌ Invalid. Reply with a number between 1 and 6."
        data["agro_ecological_zone"] = aez[msg]
        save("reg_soil", data)
        return (
            "What is your *soil type*?\n\n"
            "1. Sandy Loam\n2. Clay Loam\n"
            "3. Sandy\n4. Red Clay\n\n"
            "Reply with a number (1-4)"
        )

    if step == "reg_soil":
        soils = {"1":"Sandy Loam","2":"Clay Loam","3":"Sandy","4":"Red Clay"}
        if msg not in soils:
            return "❌ Invalid. Reply with 1, 2, 3 or 4."
        data["soil_type"] = soils[msg]
        save("reg_variety", data)
        return (
            "What *maize variety* do you grow?\n\n"
            "1. SC403\n2. SC513\n3. ZM421\n"
            "4. ZM521\n5. DKC80-73\n6. Local/OPV\n\n"
            "Reply with a number (1-6)"
        )

    if step == "reg_variety":
        varieties = {
            "1":"SC403","2":"SC513","3":"ZM421",
            "4":"ZM521","5":"DKC80-73","6":"Local/OPV"
        }
        if msg not in varieties:
            return "❌ Invalid. Reply with a number between 1 and 6."
        data["maize_variety"]  = varieties[msg]
        data["phone_number"]   = from_number
        save("reg_confirm", data)
        return (
            f"📋 *Please confirm your details:*\n\n"
            f"Name     : {data['full_name']}\n"
            f"Province : {data['province']}\n"
            f"Scale    : {data['farming_scale']}\n"
            f"Area     : {data['area_cultivated_ha']} ha\n"
            f"AEZ      : {data['agro_ecological_zone']}\n"
            f"Soil     : {data['soil_type']}\n"
            f"Variety  : {data['maize_variety']}\n\n"
            f"Reply *YES* to confirm or *NO* to restart"
        )

    if step == "reg_confirm":
        if msg == "yes":
            farmer_id, error = db_register_farmer(data)
            if farmer_id:
                save("menu", {})
                return (
                    f"✅ *Registration successful!*\n\n"
                    f"Your Farmer ID: *{farmer_id}*\n"
                    f"Save this ID — you need it for predictions.\n\n"
                    f"Reply *menu* to return to main menu."
                )
            else:
                save("menu", {})
                return f"❌ Registration failed: {error}\n\nReply *menu* to try again."
        else:
            save("menu", {})
            return "Registration cancelled. Reply *menu* to start again."

    # ── OPTION 2: PREDICT YIELD ───────────────────────────────────────────────
    if msg == "2" and step in ["menu","registered","predicted"]:
        save("pred_id", {})
        return "🌽 *Yield Prediction*\n\nPlease enter your *Farmer ID*:"

    if step == "pred_id":
        try:
            data["farmer_id"] = int(raw_msg.strip())
        except:
            return "❌ Invalid ID. Please enter a number."
        farmer = db_get_farmer(data["farmer_id"])
        if not farmer:
            return "❌ Farmer ID not found. Register first or check your ID."
        save("pred_rainfall", data)
        return (
            f"✅ Farmer found: *{farmer.full_name}*\n"
            f"Province: {farmer.province} | Scale: {farmer.farming_scale}\n\n"
            f"🌧️ What is the expected *seasonal rainfall* in mm?\n"
            f"Example: 620"
        )

    if step == "pred_rainfall":
        try:
            data["seasonal_rainfall_mm"] = float(raw_msg.strip())
        except:
            return "❌ Invalid. Enter a number. Example: 620"
        save("pred_fertilizer", data)
        return "🌱 How much *fertilizer* are you applying? (kg/ha)\n\nExample: 150"

    if step == "pred_fertilizer":
        try:
            data["fertilizer_kg_ha"] = float(raw_msg.strip())
        except:
            return "❌ Invalid. Enter a number. Example: 150"
        save("pred_irrigation", data)
        return "💧 Do you use *irrigation*?\n\n1. Yes\n2. No"

    if step == "pred_irrigation":
        if msg not in ["1","2"]:
            return "❌ Please reply 1 for Yes or 2 for No."
        data["irrigation"] = 1 if msg == "1" else 0
        save("pred_seed", data)
        return "🌾 Are you using *improved/hybrid seed*?\n\n1. Yes\n2. No"

    if step == "pred_seed":
        if msg not in ["1","2"]:
            return "❌ Please reply 1 for Yes or 2 for No."
        data["improved_seed"] = 1 if msg == "1" else 0
        save("pred_pesticide", data)
        return "🧪 Are you using *pesticides/herbicides*?\n\n1. Yes\n2. No"

    if step == "pred_pesticide":
        if msg not in ["1","2"]:
            return "❌ Please reply 1 for Yes or 2 for No."
        data["pesticide_used"] = 1 if msg == "1" else 0
        save("pred_planting", data)
        return (
            "📅 How many *days late* did you plant?\n\n"
            "Example: 0 (on time), 14 (2 weeks late)"
        )

    if step == "pred_planting":
        try:
            data["planting_date_delay_days"] = int(raw_msg.strip())
        except:
            return "❌ Invalid. Enter a whole number. Example: 7"
        save("predicting", data)

        result, error = db_predict_and_save(data["farmer_id"], data)
        if result:
            save("predicted", {"farmer_id": data["farmer_id"]})
            return (
                f"✅ *Yield Prediction Results*\n\n"
                f"👨‍🌾 Farmer    : {result['farmer']}\n"
                f"📍 Province  : {result['province']}\n"
                f"🌽 Yield/ha  : {result['predicted_yield_kg_ha']:,} kg/ha\n"
                f"📦 Total     : {result['total_yield_kg']:,} kg\n"
                f"⚖️  Tonnes    : {result['total_yield_tonnes']} t\n"
                f"💰 Price     : ${result['market_price_usd_kg']}/kg\n"
                f"💵 Revenue   : ${result['estimated_revenue_usd']:,}\n\n"
                f"Reply *3* to find buyers or *menu* to go back."
            )
        else:
            save("menu", {})
            return f"❌ Prediction failed: {error}\n\nReply *menu* to try again."

    # ── OPTION 3: FIND BUYERS ─────────────────────────────────────────────────
    if msg == "3" and step in ["menu","predicted"]:
        farmer_id = data.get("farmer_id")
        if not farmer_id:
            save("match_id", {})
            return "🤝 *Find Buyers*\n\nPlease enter your *Farmer ID*:"
        matches, error = db_match_farmer(farmer_id)
        return _format_matches(matches, error, from_number, data, save)

    if step == "match_id":
        try:
            farmer_id = int(raw_msg.strip())
        except:
            return "❌ Invalid ID. Enter a number."
        matches, error = db_match_farmer(farmer_id)
        return _format_matches(matches, error, from_number, data, save)

    # ── OPTION 4: MARKET PRICES ───────────────────────────────────────────────
    if msg == "4":
        prices  = db_get_prices()
        msg_out = "💰 *Current Maize Market Prices*\n\n"
        for p in prices:
            msg_out += (
                f"📍 {p['province']}\n"
                f"   ${p['price_usd_kg']}/kg  |  ${p['price_usd_t']}/t\n\n"
            )
        msg_out += "Reply *menu* to go back."
        return msg_out

    # ── OPTION 5: REGISTER BUYER ──────────────────────────────────────────────
    if msg == "5" and step == "menu":
        save("buyer_name", {})
        return "🏢 *Buyer Registration*\n\nPlease enter your *full name*:"

    if step == "buyer_name":
        save("buyer_company", {"full_name": raw_msg.strip()})
        return "Enter your *company name* (or reply *skip* if individual):"

    if step == "buyer_company":
        data["company_name"] = None if msg == "skip" else raw_msg.strip()
        save("buyer_province", data)
        return (
            "Which *province* are you buying from?\n\n"
            "1. Mashonaland West\n2. Mashonaland East\n"
            "3. Mashonaland Central\n4. Manicaland\n"
            "5. Masvingo\n6. Midlands\n"
            "7. Matabeleland North\n8. Matabeleland South\n\n"
            "Reply with a number (1-8)"
        )

    if step == "buyer_province":
        provinces = {
            "1":"Mashonaland West",  "2":"Mashonaland East",
            "3":"Mashonaland Central","4":"Manicaland",
            "5":"Masvingo",          "6":"Midlands",
            "7":"Matabeleland North", "8":"Matabeleland South"
        }
        if msg not in provinces:
            return "❌ Invalid. Reply with a number between 1 and 8."
        data["province"] = provinces[msg]
        save("buyer_quantity", data)
        return "📦 How many *kg* of maize do you need?\n\nExample: 5000"

    if step == "buyer_quantity":
        try:
            data["quantity_needed"] = float(raw_msg.strip())
        except:
            return "❌ Invalid. Enter a number. Example: 5000"
        save("buyer_price", data)
        return "💵 What *price per kg* (USD) are you offering?\n\nExample: 0.28"

    if step == "buyer_price":
        try:
            data["price_offered"] = float(raw_msg.strip())
        except:
            return "❌ Invalid. Enter a number. Example: 0.28"
        data["phone_number"] = from_number
        save("buyer_confirm", data)
        return (
            f"📋 *Confirm Buyer Details:*\n\n"
            f"Name     : {data['full_name']}\n"
            f"Company  : {data.get('company_name') or 'Individual'}\n"
            f"Province : {data['province']}\n"
            f"Quantity : {data['quantity_needed']:,} kg\n"
            f"Price    : ${data['price_offered']}/kg\n\n"
            f"Reply *YES* to confirm or *NO* to cancel"
        )

    if step == "buyer_confirm":
        if msg == "yes":
            buyer_id, error = db_register_buyer(data)
            if buyer_id:
                save("menu", {})
                return (
                    f"✅ *Buyer registered successfully!*\n\n"
                    f"Your Buyer ID: *{buyer_id}*\n"
                    f"We will notify you via WhatsApp when matched.\n\n"
                    f"Reply *menu* to go back."
                )
            else:
                save("menu", {})
                return f"❌ Registration failed: {error}\n\nReply *menu* to try again."
        else:
            save("menu", {})
            return "Registration cancelled. Reply *menu* to start again."

    # ── DEFAULT ───────────────────────────────────────────────────────────────
    return (
        "❓ I didn't understand that.\n\n"
        "Reply *menu* to see all options."
    )

# ── Format match response ─────────────────────────────────────────────────────
def _format_matches(matches, error, from_number, data, save):
    if error:
        save("menu", {})
        return f"❌ {error}\n\nReply *menu* to go back."
    if not matches:
        save("menu", {})
        return (
            "😔 No matching buyers found right now.\n"
            "We will notify you when a buyer is available.\n\n"
            "Reply *menu* to go back."
        )
    msg_out = f"🤝 *{len(matches)} Buyer(s) Found!*\n\n"
    for i, m in enumerate(matches, 1):
        msg_out += (
            f"*Buyer {i}*\n"
            f"👤 {m['buyer']} — {m['company']}\n"
            f"📦 Quantity : {m['quantity_kg']:,} kg\n"
            f"💵 Price    : ${m['price_usd_kg']}/kg\n"
            f"💰 Total    : ${m['total_value_usd']:,}\n"
            f"📞 Contact  : {m['buyer_phone']}\n\n"
        )
    msg_out += "Reply *menu* to go back."
    save("menu", {})
    return msg_out