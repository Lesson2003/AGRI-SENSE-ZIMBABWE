# ── FULL app.py ───────────────────────────────────────────────────────────────
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title = "Zimbabwe Maize Yield Platform",
    page_icon  = "🌽",
    layout     = "wide",
    initial_sidebar_state = "expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    [data-testid="stSidebar"] { background-color: #1F4E79; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stTextInput > label,
    .stNumberInput > label,
    .stSelectbox > label,
    .stSlider > label,
    .stRadio > label {
        color: #A9D1F7 !important;
        font-weight: bold !important;
        font-size: 15px !important;
    }
    .stTextInput input,
    .stNumberInput input {
        background-color: #1E2A3A !important;
        color: #FFFFFF !important;
        border: 1px solid #2E75B6 !important;
        border-radius: 6px !important;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #1E2A3A !important;
        color: #FFFFFF !important;
        border: 1px solid #2E75B6 !important;
    }
    .stRadio div { color: #FAFAFA !important; }
    .stFormSubmitButton button {
        background-color: #2E75B6 !important;
        color: white !important;
        font-size: 16px !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 12px !important;
        width: 100% !important;
    }
    .stFormSubmitButton button:hover { background-color: #1F4E79 !important; }
    .stButton button {
        background-color: #2E75B6 !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        border: none !important;
    }
    div[data-testid="metric-container"] {
        background-color : #1F4E79 !important;
        border           : 1px solid #2E75B6 !important;
        border-radius    : 10px !important;
        padding          : 15px !important;
    }
    div[data-testid="metric-container"] label { color: #A9D1F7 !important; }
    div[data-testid="metric-container"] div   { color: #FFFFFF !important; }
    h1, h2, h3 { color: #5BA3D9 !important; }
    .streamlit-expanderHeader {
        background-color: #1E2A3A !important;
        color: #FFFFFF !important;
    }
    hr { border-color: #2E75B6 !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/6/6a/Flag_of_Zimbabwe.svg",
    width=120
)
st.sidebar.title("🌽 Maize Platform")
st.sidebar.markdown("---")

page = st.sidebar.radio("Navigate", [
    "Dashboard",
    "Register Farmer",
    "Predict Yield",
    "Find Buyers",
    "Register Buyer",
    "Market Prices",
    "Admin Panel"
])

st.sidebar.markdown("---")
st.sidebar.markdown("**API Status**")
try:
    res = requests.get(f"{BASE_URL}/", timeout=3)
    if res.status_code == 200:
        st.sidebar.success("✅ API Online")
    else:
        st.sidebar.error("❌ API Offline")
except:
    st.sidebar.error("❌ API Offline — start uvicorn")

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
if page == "Dashboard":
    st.title("🌽 AGRI-SENSE ZIMBABWE")
    st.markdown("### Connecting Farmers to Buyers With Ease")
    st.markdown("---")

    try:
        farmers = requests.get(f"{BASE_URL}/farmers").json()
        buyers  = requests.get(f"{BASE_URL}/buyers").json()
        prices  = requests.get(f"{BASE_URL}/prices").json()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👨‍🌾 Registered Farmers", farmers["total"])
        col2.metric("🏢 Active Buyers",        buyers["total"])
        col3.metric("💰 Avg Price (USD/kg)",
                    f"${round(sum(p['price_usd_kg'] for p in prices['prices'][:8]) / 8, 3)}")
        col4.metric("🌍 Provinces Covered", "8")

        st.markdown("---")

        if farmers["total"] > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📍 Farmers by Province")
                farm_df     = pd.DataFrame(farmers["farmers"])
                prov_counts = farm_df["province"].value_counts().reset_index()
                prov_counts.columns = ["Province", "Count"]
                fig = px.bar(prov_counts, x="Count", y="Province",
                             orientation="h", color="Count",
                             color_continuous_scale="Blues",
                             template="plotly_dark")
                fig.update_layout(height=350, paper_bgcolor="#0E1117",
                                  plot_bgcolor="#0E1117")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("🏭 Farmers by Scale")
                scale_counts = farm_df["scale"].value_counts().reset_index()
                scale_counts.columns = ["Scale", "Count"]
                fig2 = px.pie(scale_counts, names="Scale", values="Count",
                              color_discrete_sequence=["#1F4E79","#2E75B6","#5BA3D9"],
                              template="plotly_dark")
                fig2.update_layout(paper_bgcolor="#0E1117")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No farmers registered yet. Go to 👨‍🌾 Register Farmer to add one.")

        st.subheader("💰 Current Market Prices by Province")
        seen = {}
        for p in prices["prices"]:
            if p["province"] not in seen:
                seen[p["province"]] = p
        price_df = pd.DataFrame(seen.values())
        fig3 = px.bar(price_df, x="province", y="price_usd_kg",
                      color="price_usd_kg", color_continuous_scale="Greens",
                      labels={"price_usd_kg": "Price (USD/kg)", "province": "Province"},
                      template="plotly_dark")
        fig3.update_layout(height=350, paper_bgcolor="#0E1117",
                           plot_bgcolor="#0E1117")
        st.plotly_chart(fig3, use_container_width=True)

    except Exception as e:
        st.error(f"Could not load dashboard: {e}")

# ── REGISTER FARMER ───────────────────────────────────────────────────────────
elif page == "Register Farmer":
    st.title("👨Farmer Registration")
    st.markdown("Fill in all fields below to register a new farmer.")
    st.markdown("---")

    with st.form("farmer_form"):
        st.markdown("#### 👤 Personal Details")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", placeholder="e.g. John Moyo")
            phone     = st.text_input("WhatsApp Number", placeholder="+263771234567")
        with col2:
            province  = st.selectbox("Province", [
                "Mashonaland West","Mashonaland East","Mashonaland Central",
                "Manicaland","Masvingo","Midlands",
                "Matabeleland North","Matabeleland South"
            ])
            scale     = st.selectbox("Farming Scale", [
                "Smallholder","Small Commercial","Large Commercial"
            ])

        st.markdown("#### 🌱 Farm Details")
        col3, col4 = st.columns(2)
        with col3:
            area    = st.number_input("Area Cultivated (ha)",
                                       min_value=0.1, value=2.5, step=0.1)
            aez     = st.selectbox("Agro-Ecological Zone",
                                    ["I","II","IIb","III","IV","V"])
        with col4:
            soil    = st.selectbox("Soil Type", [
                "Sandy Loam","Clay Loam","Sandy","Red Clay"
            ])
            variety = st.selectbox("Maize Variety", [
                "SC403","SC513","ZM421","ZM521","DKC80-73","Local/OPV"
            ])

        st.markdown("---")
        submitted = st.form_submit_button("✅ Register Farmer", use_container_width=True)

        if submitted:
            if not full_name or not phone:
                st.error("❌ Full Name and WhatsApp Number are required.")
            else:
                res = requests.post(f"{BASE_URL}/farmers/register", json={
                    "full_name"            : full_name,
                    "phone_number"         : phone,
                    "province"             : province,
                    "farming_scale"        : scale,
                    "area_cultivated_ha"   : area,
                    "agro_ecological_zone" : aez,
                    "soil_type"            : soil,
                    "maize_variety"        : variety
                })
                if res.status_code == 200:
                    farmer_id = res.json()["farmer_id"]
                    st.success(f"✅ Farmer registered! Farmer ID: **{farmer_id}**")
                    st.info(f"📱 Farmer can use WhatsApp bot with ID: {farmer_id}")
                else:
                    st.error(f"❌ {res.json().get('detail','Registration failed.')}")

# ── PREDICT YIELD ─────────────────────────────────────────────────────────────
elif page == "Predict Yield":
    st.title("Predict Maize Yield")
    st.markdown("Enter the seasonal conditions to predict expected yield.")
    st.markdown("---")

    # Step 1: Load farmer profile
    st.markdown("#### 🆔 Enter Farmer ID to load profile")
    col1, col2 = st.columns([2, 1])
    with col1:
        farmer_id = st.number_input("Farmer ID", min_value=1, step=1, value=1,
                                     label_visibility="collapsed")
    with col2:
        load = st.button("🔍 Load Farmer Profile", use_container_width=True)

    if load:
        res = requests.get(f"{BASE_URL}/farmers/{int(farmer_id)}")
        if res.status_code == 200:
            st.session_state["farmer"] = res.json()
            st.success("✅ Farmer profile loaded!")
        else:
            st.error("❌ Farmer not found. Register the farmer first.")
            st.session_state.pop("farmer", None)

    # Step 2: Show farmer profile
    if "farmer" in st.session_state:
        f = st.session_state["farmer"]

        st.markdown("---")
        st.markdown("### Farmer Profile ")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👨‍🌾 Name",          f["full_name"])
        col2.metric("📍 Province",       f["province"])
        col3.metric("🏭 Farming Scale",  f["farming_scale"])
        col4.metric("🌍 AEZ",            f["agro_ecological_zone"])

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("🌱 Area (ha)",      f["area_cultivated_ha"])
        col6.metric("🪨 Soil Type",      f["soil_type"])
        col7.metric("🌽 Variety",        f["maize_variety"])
        col8.metric("📞 Phone",          f["phone_number"])

        st.info(
            "✅ Features from profile used in model: "
            "**Province**, **Farming Scale**, **AEZ**, **Area Cultivated**"
        )

        # Step 3: Seasonal inputs
        st.markdown("---")
        st.markdown("#### 🌧️  Enter Seasonal Conditions")

        with st.form("predict_form"):
            st.markdown("**Seasonal Conditions:**")
            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🌧️ Seasonal Rainfall (mm)**")
                rainfall   = st.slider("Rainfall", 150, 1100, 620,
                                        label_visibility="collapsed")
                st.caption(f"Selected: {rainfall} mm")

                st.markdown("**🌱 Fertilizer Applied (kg/ha)**")
                fertilizer = st.slider("Fertilizer", 0, 300, 150,
                                        label_visibility="collapsed")
                st.caption(f"Selected: {fertilizer} kg/ha")

                st.markdown("**📅 Planting Date Delay (days after optimal)**")
                delay      = st.slider("Delay", 0, 30, 0,
                                        label_visibility="collapsed")
                st.caption(f"Selected: {delay} days")

            with col2:
                st.markdown("**💧 Irrigation Used?**")
                irrigation    = st.radio("Irrigation", ["No","Yes"],
                                          horizontal=True,
                                          label_visibility="collapsed")

                st.markdown("**🌾 Improved / Hybrid Seed?**")
                improved_seed = st.radio("Seed", ["No","Yes"],
                                          horizontal=True,
                                          label_visibility="collapsed")

                st.markdown("**🧪 Pesticide / Herbicide Applied?**")
                pesticide     = st.radio("Pesticide", ["No","Yes"],
                                          horizontal=True,
                                          label_visibility="collapsed")

            st.markdown("---")
            st.markdown("#### Features Summary")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
| Feature | Value | Source |
|---|---|---|
| Province | {f['province']} | 🗄️ DB |
| Farming Scale | {f['farming_scale']} | 🗄️ DB |
| AEZ Ordinal | {f['agro_ecological_zone']} | 🗄️ DB |
| Area Cultivated (ha) | {f['area_cultivated_ha']} | 🗄️ DB |
| Seasonal Rainfall (mm) | {rainfall} | 📝 Form |
                """)
            with col2:
                st.markdown(f"""
| Feature | Value | Source |
|---|---|---|
| Fertilizer (kg/ha) | {fertilizer} | 📝 Form |
| Irrigation | {'Yes' if irrigation=='Yes' else 'No'} | 📝 Form |
| Improved Seed | {'Yes' if improved_seed=='Yes' else 'No'} | 📝 Form |
| Pesticide Used | {'Yes' if pesticide=='Yes' else 'No'} | 📝 Form |
| Planting Delay (days) | {delay} | 📝 Form |
                """)

            st.markdown("---")
            submitted = st.form_submit_button("🔮 Predict Yield", use_container_width=True)

            if submitted:
                res = requests.post(f"{BASE_URL}/predict", json={
                    "farmer_id"               : int(farmer_id),
                    "seasonal_rainfall_mm"    : rainfall,
                    "fertilizer_kg_ha"        : fertilizer,
                    "irrigation"              : 1 if irrigation == "Yes" else 0,
                    "improved_seed"           : 1 if improved_seed == "Yes" else 0,
                    "pesticide_used"          : 1 if pesticide == "Yes" else 0,
                    "planting_date_delay_days": delay
                })

                if res.status_code == 200:
                    r = res.json()
                    st.success("✅ Prediction Complete!")
                    st.markdown("---")

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("🌽 Yield/ha",     f"{r['predicted_yield_kg_ha']:,} kg")
                    col2.metric("📦 Total Yield",  f"{r['total_yield_kg']:,} kg")
                    col3.metric("⚖️ Tonnes",        f"{r['total_yield_tonnes']} t")
                    col4.metric("💵 Est. Revenue", f"${r['estimated_revenue_usd']:,}")

                    col1, col2, col3 = st.columns(3)
                    col1.info(f"**📍 Province:** {r['province']}")
                    col2.info(f"**🌍 Area:** {r['area_ha']} ha")
                    col3.info(f"**💰 Market Price:** ${r['market_price_usd_kg']}/kg")

                    fig = go.Figure(go.Indicator(
                        mode  = "gauge+number",
                        value = r['predicted_yield_kg_ha'],
                        title = {"text": "Predicted Yield (kg/ha)",
                                 "font": {"color": "white"}},
                        number= {"font": {"color": "white"}},
                        gauge = {
                            "axis"   : {"range": [0, 12000], "tickcolor": "white"},
                            "bar"    : {"color": "#2E75B6"},
                            "bgcolor": "#1E2A3A",
                            "steps"  : [
                                {"range": [0,    2000], "color": "#E76F51"},
                                {"range": [2000, 5000], "color": "#F4A261"},
                                {"range": [5000,12000], "color": "#2A9D8F"},
                            ],
                        }
                    ))
                    fig.update_layout(height=300, paper_bgcolor="#0E1117",
                                      font={"color": "white"})
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.error(f"❌ {res.json().get('detail','Prediction failed.')}")

    else:
        st.warning(
            "⚠️ Enter a Farmer ID above and click "
            "**Load Farmer Profile** to begin."
        )

# ── FIND BUYERS ───────────────────────────────────────────────────────────────
elif page == "Find Buyers":
    st.title("🤝 Match Farmer to Buyers")
    st.markdown("Find the best buyers for a farmer based on predicted yield.")
    st.markdown("---")

    st.markdown("#### 🆔 Enter Farmer ID")
    farmer_id = st.number_input("Farmer ID", min_value=1, step=1, value=1,
                                 label_visibility="collapsed")

    if st.button("🔍 Find Matching Buyers", use_container_width=True):
        res = requests.post(f"{BASE_URL}/match/{int(farmer_id)}")
        if res.status_code == 200:
            data = res.json()
            if "matches" in data and len(data["matches"]) > 0:
                st.success(
                    f"✅ {len(data['matches'])} buyer(s) matched "
                    f"for {data['farmer']}!"
                )
                st.markdown("---")
                for i, m in enumerate(data["matches"], 1):
                    with st.expander(
                        f"🏢 Buyer {i} — {m['buyer']} | ${m['price_usd_kg']}/kg",
                        expanded=True
                    ):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("🏢 Company",    m.get("company") or "Individual")
                        col2.metric("📦 Quantity",   f"{m['quantity_kg']:,} kg")
                        col3.metric("💵 Deal Value", f"${m['total_value_usd']:,}")
                        st.info(f"📞 WhatsApp Contact: {m['buyer_phone']}")
            else:
                st.warning("⚠️ No matching buyers found. Register buyers first.")
        else:
            st.error(f"❌ {res.json().get('detail','Error.')}")

# ── REGISTER BUYER ────────────────────────────────────────────────────────────
elif page == "Register Buyer":
    st.title("🏢 Buyer Registration")
    st.markdown("Register a grain buyer or trading company.")
    st.markdown("---")

    with st.form("buyer_form"):
        st.markdown("#### 👤 Buyer Details")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name",
                                       placeholder="e.g. David Chikwanda")
            phone     = st.text_input("WhatsApp Number",
                                       placeholder="+263772345678")
            company   = st.text_input(
                "Company Name (leave blank if individual)",
                placeholder="e.g. Grain Millers Zimbabwe"
            )
        with col2:
            province  = st.selectbox("Province", [
                "Mashonaland West","Mashonaland East","Mashonaland Central",
                "Manicaland","Masvingo","Midlands",
                "Matabeleland North","Matabeleland South"
            ])
            quantity  = st.number_input("Quantity Needed (kg)",
                                         min_value=100.0, value=5000.0)
            price     = st.number_input("Price Offered (USD/kg)",
                                         min_value=0.01, value=0.28, step=0.01)

        st.markdown("---")
        submitted = st.form_submit_button("✅ Register Buyer", use_container_width=True)

        if submitted:
            if not full_name or not phone:
                st.error("❌ Full Name and WhatsApp Number are required.")
            else:
                res = requests.post(f"{BASE_URL}/buyers/register", json={
                    "full_name"      : full_name,
                    "phone_number"   : phone,
                    "company_name"   : company or None,
                    "province"       : province,
                    "quantity_needed": quantity,
                    "price_offered"  : price
                })
                if res.status_code == 200:
                    st.success(
                        f"✅ Buyer registered! ID: **{res.json()['buyer_id']}**"
                    )
                    st.info(
                        "📱 Buyer will be notified via WhatsApp "
                        "when matched with a farmer."
                    )
                else:
                    st.error(
                        f"❌ {res.json().get('detail','Registration failed.')}"
                    )

# ── MARKET PRICES ─────────────────────────────────────────────────────────────
elif page == "Market Prices":
    st.title("💰 Maize Market Prices")
    st.markdown("Current maize prices across Zimbabwe provinces.")
    st.markdown("---")

    res = requests.get(f"{BASE_URL}/prices")
    if res.status_code == 200:
        seen = {}
        for p in res.json()["prices"]:
            if p["province"] not in seen:
                seen[p["province"]] = p
        price_df = pd.DataFrame(seen.values())

        fig = px.bar(price_df, x="province", y="price_usd_kg",
                     color="price_usd_kg", color_continuous_scale="Greens",
                     labels={"price_usd_kg": "Price (USD/kg)",
                             "province": "Province"},
                     template="plotly_dark")
        fig.update_layout(height=400, paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            price_df[["province","price_usd_kg","price_usd_t","source"]]
            .rename(columns={
                "province"    : "Province",
                "price_usd_kg": "Price (USD/kg)",
                "price_usd_t" : "Price (USD/tonne)",
                "source"      : "Source"
            }),
            use_container_width=True
        )

    st.markdown("---")
    st.subheader("✏️ Update Market Price")
    with st.form("price_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            upd_province = st.selectbox("Province", [
                "Mashonaland West","Mashonaland East","Mashonaland Central",
                "Manicaland","Masvingo","Midlands",
                "Matabeleland North","Matabeleland South"
            ])
        with col2:
            upd_price  = st.number_input("New Price (USD/kg)",
                                          min_value=0.01, value=0.28, step=0.01)
        with col3:
            upd_source = st.text_input("Source", value="Manual Entry")

        if st.form_submit_button("💾 Update Price", use_container_width=True):
            res = requests.post(f"{BASE_URL}/prices/update", json={
                "province"    : upd_province,
                "price_usd_kg": upd_price,
                "source"      : upd_source
            })
            if res.status_code == 200:
                st.success(
                    f"✅ Price updated for {upd_province} — ${upd_price}/kg"
                )
                st.rerun()
            else:
                st.error("❌ Failed to update price.")

# ── ADMIN PANEL ───────────────────────────────────────────────────────────────
elif page == "Admin Panel":
    st.title("Admin Panel")
    st.markdown("Manage all farmers and buyers in the database.")
    st.markdown("---")

    tab1, tab2 = st.tabs(["👨‍🌾 All Farmers", "🏢 All Buyers"])

    with tab1:
        res = requests.get(f"{BASE_URL}/farmers")
        if res.status_code == 200:
            data = res.json()
            st.metric("Total Active Farmers", data["total"])
            st.markdown("---")
            if data["total"] > 0:
                df = pd.DataFrame(data["farmers"])
                st.dataframe(df, use_container_width=True)
                st.markdown("---")
                st.subheader("🗑️ Deactivate Farmer")
                col1, col2 = st.columns([2, 1])
                with col1:
                    del_id = st.number_input("Enter Farmer ID to deactivate",
                                              min_value=1, step=1)
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Deactivate", type="primary"):
                        res2 = requests.delete(
                            f"{BASE_URL}/farmers/{int(del_id)}"
                        )
                        if res2.status_code == 200:
                            st.success(res2.json()["message"])
                            st.rerun()
                        else:
                            st.error("❌ Failed.")
            else:
                st.info("No farmers registered yet.")

    with tab2:
        res = requests.get(f"{BASE_URL}/buyers")
        if res.status_code == 200:
            data = res.json()
            st.metric("Total Active Buyers", data["total"])
            st.markdown("---")
            if data["total"] > 0:
                df = pd.DataFrame(data["buyers"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No buyers registered yet.")