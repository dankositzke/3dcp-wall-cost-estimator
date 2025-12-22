import streamlit as st
import pandas as pd
import altair as alt

# ---------------------------------------------------------
# 0. CONSTANTS & CONVERSIONS (High Precision)
# ---------------------------------------------------------
SQ_M_TO_SQ_FT = 10.7639104
TONNE_TO_TON = 1.10231
KG_M3_TO_LBS_FT3 = 0.06242796
MM_TO_FT = 0.00328084
MM_TO_INCH = 0.0393701
M_TO_FT = 3.28084

# ---------------------------------------------------------
# 1. THE DATABASE (Source of Truth in IMPERIAL / USD)
# ---------------------------------------------------------
PRINTERS = {
    "COBOD BOD2": {
        "price": 580000,          # Includes batch plant/pump. Base gantry is ~$420k.
        "speed_mm_s": 250,        # Operational max with safety (Max theoretical is 1000)
        "setup_days": 2.0,        # Realistic site prep + assembly
        "teardown_days": 1.5,
        "crew_size": 3,           # Operator + Material Handler + Helper
        "efficiency": 0.65,       # OEE (Overall Equipment Effectiveness)
        "bead_width_mm": 50,      # Standard nozzle
        "layer_height_mm": 20
    },
    "CyBe RC (Robot Crawler)": {
        "price": 230000,          # ~$205k EUR base + logistics
        "speed_mm_s": 250,        # Max is 500, but 250 is typical for quality
        "setup_days": 0.5,        # Highly mobile, tracks
        "teardown_days": 0.5,
        "crew_size": 2,
        "efficiency": 0.60,
        "bead_width_mm": 40,
        "layer_height_mm": 15
    },
    "Black Buffalo NEXCON 1G": {
        "price": 850000,          # Heavy industrial gantry, ICC-ES certified path
        "speed_mm_s": 200,        # Capped for OSHA/Safety compliance
        "setup_days": 3.0,        # Heavier gantry requires crane/telehandler
        "teardown_days": 2.0,
        "crew_size": 3,
        "efficiency": 0.75,       # Designed for 12hr+ continuous runs
        "bead_width_mm": 60,
        "layer_height_mm": 25
    },
    "MudBots (25x25 Model)": {
        "price": 145000,          # Budget-friendly gantry option
        "speed_mm_s": 100,        # Slower travel speeds
        "setup_days": 2.0,
        "teardown_days": 2.0,
        "crew_size": 3,
        "efficiency": 0.55,
        "bead_width_mm": 40,
        "layer_height_mm": 20
    },
    "WASP Crane": {
        "price": 175000,          # ~$160k USD base
        "speed_mm_s": 150,
        "setup_days": 1.0,        # Modular assembly
        "teardown_days": 1.0,
        "crew_size": 2,
        "efficiency": 0.50,
        "bead_width_mm": 40,
        "layer_height_mm": 15
    },
    "RIC Technology RIC-M1 PRO": {
        "price": 250000,          # Modular robotic arm system
        "speed_mm_s": 200,        # Balance of speed and precision
        "setup_days": 0.2,        # ~2-4 hours setup (rapid deployment)
        "teardown_days": 0.2,
        "crew_size": 2,
        "efficiency": 0.70,
        "bead_width_mm": 50,
        "layer_height_mm": 20
    },
    "X-Hab 3D MX3DP": {
        "price": 450000,          # Expeditionary unit (ruggedized + tracks)
        "speed_mm_s": 250,        # Variable depending on material
        "setup_days": 0.1,        # <1 hour (designed for military/disaster relief)
        "teardown_days": 0.1,
        "crew_size": 3,           # Recommended crew for expeditionary ops
        "efficiency": 0.65,
        "bead_width_mm": 45,
        "layer_height_mm": 20
    },
    "Coral 3DCP (Mobile Unit)": {
        "price": 350000,          # Estimated hardware value (Arm + Tracks + 2K Pump)
        "speed_mm_s": 330,        # Standard op speed (Max 600 mm/s with 2K mix)
        "setup_days": 0.2,        # ~1 hour setup
        "teardown_days": 0.2,
        "crew_size": 2,
        "efficiency": 0.80,       # High efficiency due to continuous 2K flow
        "bead_width_mm": 60,      # Optimized for 3:1 aspect ratio (60mm wide)
        "layer_height_mm": 20     # (20mm high)
    },
    "Alquist 3D A1X": {
        "price": 450000,          # System Value (Leased via FMGI/Hugg & Hall)
        "speed_mm_s": 200,        # Standard KUKA arm speeds
        "setup_days": 1.0,        # Service team mobilization
        "teardown_days": 1.0,
        "crew_size": 3,           # Operated by partner service teams
        "efficiency": 0.70,
        "bead_width_mm": 50,
        "layer_height_mm": 20
    },
    "SQ4D ARCS": {
        "price": 400000,          # Estimated gantry + plant package
        "speed_mm_s": 250,        # High volume deposition
        "setup_days": 2.5,        # Heavy truss system
        "teardown_days": 2.0,
        "crew_size": 3,
        "efficiency": 0.75,       # Optimized for long straight walls
        "bead_width_mm": 80,      # Wide bead for structural walls
        "layer_height_mm": 25
    }
}

MATERIALS = {
    "Sika Sikacrete®-751 3D": {
        "type": "Premix",
        "price_ton": 450,         # Confirmed ~ $450/super sack
        "density_lbs_ft3": 137,   # ~2200 kg/m3
        "waste_pct": 0.03,        # Very consistent factory mix
        "open_time_min": 60
    },
    "Laticrete 3DCP": {
        "type": "Premix",
        "price_ton": 480,
        "density_lbs_ft3": 135,
        "waste_pct": 0.04,
        "open_time_min": 45
    },
    "Local Concrete + D.fab": {
        "type": "Admix",
        "price_ton": 55,          # ~$40-60/ton. 99% local sand/cement + 1% D.fab
        "density_lbs_ft3": 145,   # Standard concrete density ~2300 kg/m3
        "waste_pct": 0.10,        # Higher waste due to onsite batching variance
        "open_time_min": 30
    },
    "CyBe Mortar": {
        "type": "Premix",
        "price_ton": 350,         # Lower cost European base, fast set
        "density_lbs_ft3": 131,   # ~2100 kg/m3
        "waste_pct": 0.05,
        "open_time_min": 5        # Extremely fast set (3 min)
    },
    "Mapei Planitop 3D": {
        "type": "Premix",
        "price_ton": 500,         # Premium fiber-reinforced mortar
        "density_lbs_ft3": 137,   # 2200 kg/m3
        "waste_pct": 0.03,
        "open_time_min": 60       # Retains consistency for stacking
    },
    "Heidelberg i.tech 3D": {
        "type": "Premix",
        "price_ton": 480,         # Mineral-based dry mortar
        "density_lbs_ft3": 134,   # 2150 kg/m3
        "waste_pct": 0.04,
        "open_time_min": 28       # Thixotropic open time
    },
    "Holcim TectorPrint": {
        "type": "Premix",
        "price_ton": 470,         # High compressive strength range
        "density_lbs_ft3": 146,   # ~2350 kg/m3 (High density)
        "waste_pct": 0.03,
        "open_time_min": 40
    },
    "Eco Material PozzoCEM": {
        "type": "Green-Mix",
        "price_ton": 50,          # Low cost green cement replacement
        "density_lbs_ft3": 145,   # Standard concrete density
        "waste_pct": 0.08,
        "open_time_min": 3        # Very fast set (2-3 min)
    },
    "Coral 2K Concrete (Local)": {
        "type": "Admix-2K",
        "price_ton": 60,          # Local concrete + accelerator at nozzle
        "density_lbs_ft3": 145,
        "waste_pct": 0.12,        # Higher start/stop waste with 2K
        "open_time_min": 1        # Instant set at nozzle
    }
}

# ---------------------------------------------------------
# 2. PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="3DCP Cost Estimator", page_icon="🏗️", layout="wide")

st.title("🏗️ 3DCP Construction Cost Estimator")
st.markdown("### From Print-to-Keys: Economic Modeling")
st.divider()

# ---------------------------------------------------------
# 3. MAIN CONTROL PANEL
# ---------------------------------------------------------
with st.container(border=True):
    st.markdown("#### Project Configuration")
    
    # Unit Toggle
    unit_col, _ = st.columns([1, 2])
    with unit_col:
        unit_system = st.radio("Unit System:", ["Imperial (US)", "Metric (EU)"], horizontal=True)
    
    is_metric = unit_system == "Metric (EU)"
    
    # 4 Columns for Main Inputs
    c1, c2, c3, c4 = st.columns(4)
    
    printer_names = list(PRINTERS.keys())
    material_names = list(MATERIALS.keys())
    
    try:
        dfab_index = material_names.index("Local Concrete + D.fab")
    except ValueError:
        dfab_index = 0

    with c1:
        selected_printer = st.selectbox("Select Printer", printer_names, index=0)
    with c2:
        selected_material = st.selectbox("Select Material Strategy", material_names, index=dfab_index)
    with c3:
        num_homes = st.number_input("Number of Homes In Project", min_value=1, value=10)
    with c4:
        # Area Input
        IMPERIAL_DEFAULT_SQFT = 1500
        if is_metric:
            default_sqm = int(IMPERIAL_DEFAULT_SQFT / SQ_M_TO_SQ_FT)
            sq_m_input = st.number_input("Avg. Sq Meters", value=default_sqm, step=1, format="%d")
            sq_ft_home = sq_m_input * SQ_M_TO_SQ_FT 
        else:
            sq_ft_home = st.number_input("Avg. Sq Ft", value=IMPERIAL_DEFAULT_SQFT, step=10, format="%d")

# ---------------------------------------------------------
# 4. ADVANCED OVERRIDES (Fully Exposed)
# ---------------------------------------------------------
printer_defaults = PRINTERS[selected_printer]
mat_defaults = MATERIALS[selected_material]

st.write("") # Spacer

with st.expander("🛠️ Advanced Assumptions (Click to Edit)"):
    # We use Tabs to organize the variables cleanly
    tab_fin, tab_geo, tab_ops = st.tabs(["💵 Financials", "📐 Geometry & Design", "⚙️ Operations & Labor"])

    # --- TAB 1: FINANCIALS ---
    with tab_fin:
        f1, f2, f3 = st.columns(3)
        with f1:
            st.markdown("**Material Costs**")
            # Price
            if is_metric:
                def_price = int(mat_defaults["price_ton"] / (1/TONNE_TO_TON)) 
                u_price = st.number_input("Material Price ($/Tonne)", value=def_price, step=10)
                mat_price_ton = u_price * (1/TONNE_TO_TON)
            else:
                mat_price_ton = st.number_input("Material Price ($/Ton)", value=int(mat_defaults["price_ton"]), step=10)
            
            # Waste %
            waste_pct_in = st.number_input("Material Waste %", value=float(mat_defaults["waste_pct"]*100), step=1.0, format="%.1f")
            waste_pct = waste_pct_in / 100.0

        with f2:
            st.markdown("**Labor & Logistics**")
            labor_rate = st.number_input("Crew Labor Rate ($/hr)", value=40, step=5)
            crane_rate = st.number_input("Crane Rate ($/day)", value=1500, step=100)

        with f3:
            st.markdown("**Asset (Printer)**")
            # NEW: Printer Price Exposed
            printer_price = st.number_input("Printer Hardware Cost ($)", value=int(printer_defaults["price"]), step=5000)
            
            depreciation_years = st.number_input("Amortization Period (Yrs)", value=5)
            residual_val = st.number_input("Residual Value (%)", value=20, step=5)
            residual_value_pct = residual_val / 100.0
            est_prints_per_year = st.number_input("Annual Utilization (Homes/Yr)", value=12)

    # --- TAB 2: GEOMETRY ---
    with tab_geo:
        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown("**Wall Dimensions**")
            wall_density = st.number_input("Wall Density Factor", value=0.20, format="%.2f", help="Linear wall ft per sq ft of floor.")
            
            # Wall Height
            if is_metric:
                wall_height_m = st.number_input("Wall Height (m)", value=2.75, step=0.1)
                wall_height_ft = wall_height_m * M_TO_FT
            else:
                wall_height_ft = st.number_input("Wall Height (ft)", value=9.0, step=0.5)

            passes_per_layer = st.number_input("Passes per Layer", value=2, min_value=1, max_value=4, help="1 for hollow/thin, 2 for standard double shell.")

        with g2:
            st.markdown("**Print Resolution**")
            # Layer/Bead logic
            if is_metric:
                layer_h_mm = st.number_input("Layer Height (mm)", value=float(printer_defaults["layer_height_mm"]), step=1.0)
                bead_w_mm = st.number_input("Bead Width (mm)", value=float(printer_defaults["bead_width_mm"]), step=1.0)
            else:
                def_layer_in = printer_defaults["layer_height_mm"] * MM_TO_INCH
                def_bead_in = printer_defaults["bead_width_mm"] * MM_TO_INCH
                u_layer_in = st.number_input("Layer Height (in)", value=float(f"{def_layer_in:.3f}"), format="%.3f")
                u_bead_in = st.number_input("Bead Width (in)", value=float(f"{def_bead_in:.3f}"), format="%.3f")
                layer_h_mm = u_layer_in / MM_TO_INCH
                bead_w_mm = u_bead_in / MM_TO_INCH

        with g3:
            st.markdown("**Material Properties**")
            # Density Exposed
            if is_metric:
                def_dens = int(mat_defaults["density_lbs_ft3"] / KG_M3_TO_LBS_FT3)
                u_dens = st.number_input("Dry Density (kg/m³)", value=def_dens, step=10)
                final_density_lbs_ft3 = u_dens * KG_M3_TO_LBS_FT3
            else:
                final_density_lbs_ft3 = st.number_input("Dry Density (lbs/ft³)", value=int(mat_defaults["density_lbs_ft3"]), step=1)

    # --- TAB 3: OPERATIONS ---
    with tab_ops:
        o1, o2, o3 = st.columns(3)
        with o1:
            st.markdown("**Speed & Efficiency**")
            # Speed Exposed
            print_speed_mm_s = st.number_input("Print Speed (mm/s)", value=int(printer_defaults["speed_mm_s"]), step=10)
            efficiency_pct = st.number_input("Machine Efficiency (OEE %)", value=int(printer_defaults["efficiency"]*100), step=5)
            efficiency = efficiency_pct / 100.0

        with o2:
            st.markdown("**Site Crew**")
            crew_size = st.number_input("Crew Size (People)", value=int(printer_defaults["crew_size"]), step=1)
            moves_count = st.number_input("Printer Moves (Crane Lifts)", value=max(1, int(num_homes/2)))

        with o3:
            st.markdown("**Mobilization**")
            setup_days = st.number_input("Setup Days (per move)", value=float(printer_defaults["setup_days"]), step=0.5)
            teardown_days = st.number_input("Teardown Days (per move)", value=float(printer_defaults["teardown_days"]), step=0.5)


# ---------------------------------------------------------
# 5. THE PHYSICS ENGINE
# ---------------------------------------------------------

# A. Geometry
linear_wall_ft = sq_ft_home * wall_density
wall_height_mm = wall_height_ft * 304.8
total_layers = wall_height_mm / layer_h_mm
total_path_length_ft = linear_wall_ft * total_layers * passes_per_layer

# B. Time (Using new speed/efficiency inputs)
speed_ft_hr = print_speed_mm_s * 11.811
theoretical_time_hr = total_path_length_ft / speed_ft_hr
real_print_time_hr = theoretical_time_hr / efficiency

# C. Material (Using new waste input)
vol_cu_ft = total_path_length_ft * (layer_h_mm * MM_TO_FT) * (bead_w_mm * MM_TO_FT)
weight_lbs = vol_cu_ft * final_density_lbs_ft3
weight_tons = weight_lbs / 2000
total_mat_cost_per_home = weight_tons * mat_price_ton * (1 + waste_pct)

# D. Labor (Using new crew/setup inputs)
# Note: Setup/Teardown happens once per 'move', but we amortize per home
total_moves = moves_count # User input or calculated
setup_hrs = setup_days * 8
teardown_hrs = teardown_days * 8
print_hrs_total = real_print_time_hr * num_homes

# Project Setup Labor = (Setup + Teardown) * Moves * Crew * Rate
total_setup_labor_project = (setup_hrs + teardown_hrs) * total_moves * crew_size * labor_rate
print_labor_total = print_hrs_total * crew_size * labor_rate

total_labor_cost_per_home = (total_setup_labor_project / num_homes) + (print_labor_total / num_homes)

# E. Machine & Logistics
# Using the NEW printer_price variable
machine_cost_per_year = (printer_price * (1 - residual_value_pct)) / depreciation_years
machine_cost_per_home = machine_cost_per_year / est_prints_per_year

total_crane_days = (setup_days + teardown_days) * total_moves
total_logistics_cost = total_crane_days * crane_rate
logistics_cost_per_home = total_logistics_cost / num_homes

# F. GRAND TOTAL
grand_total = total_mat_cost_per_home + total_labor_cost_per_home + machine_cost_per_home + logistics_cost_per_home

# ---------------------------------------------------------
# 6. DASHBOARD
# ---------------------------------------------------------

st.markdown("### 💰 Cost Estimation Results")

c1, c2, c3 = st.columns([2, 1, 1])
c1.metric(label="TOTAL COST PER SHELL", value=f"${grand_total:,.0f}", delta="Estimated")
c2.write("") 

st.divider()

# PREPARE DATA
cost_data = pd.DataFrame([
    {"Category": "Material", "Cost": total_mat_cost_per_home},
    {"Category": "Labor", "Cost": total_labor_cost_per_home},
    {"Category": "Printer", "Cost": machine_cost_per_home},
    {"Category": "Logistics", "Cost": logistics_cost_per_home}
])
cost_data["% of Total"] = cost_data["Cost"] / grand_total

g1, g2 = st.columns([1, 1])

# --- MARKET PARITY ---
with g1:
    with st.container(border=True):
        st.markdown("##### 🆚 Market Benchmark")
        st.markdown("Compare 3D printed shell cost against traditional methods.")
        
        print_cost_sqft = grand_total / sq_ft_home
        
        if is_metric:
            trad_cost_sqm = st.slider("Traditional Cost (€/m²)", min_value=100, max_value=400, value=250, step=10)
            trad_cost_sqft = trad_cost_sqm / SQ_M_TO_SQ_FT
            current_unit_cost = print_cost_sqft * SQ_M_TO_SQ_FT
            unit_label = "€/m²"
        else:
            trad_cost_sqft = st.slider("Traditional Cost ($/SqFt)", min_value=10, max_value=60, value=25, step=1)
            current_unit_cost = print_cost_sqft
            unit_label = "$/SqFt"
        
        savings = (trad_cost_sqft * sq_ft_home) - grand_total
        
        st.markdown("---")
        
        if savings > 0:
            st.success(f"✅ **3D printing will save you money!**")
            st.metric("Total Project Savings (per home)", f"${savings:,.0f}", delta=f"{savings/grand_total*100:.1f}% Cheaper")
        else:
            st.error(f"❌ **3D printing is currently more expensive.**")
            st.metric("Cost Premium (per home)", f"${savings:,.0f}", delta=f"{savings/grand_total*100:.1f}% Premium", delta_color="inverse")
            
        st.caption(f"Your Print Cost: **{current_unit_cost:.2f} {unit_label}** vs Market: **{trad_cost_sqft if not is_metric else trad_cost_sqm} {unit_label}**")

# --- CHART ---
with g2:
    with st.container(border=True):
        st.markdown("##### Cost Components (Chart)")
        bar = alt.Chart(cost_data).mark_bar().encode(
            x=alt.X('Category', sort='-y'),
            y=alt.Y('Cost', axis=alt.Axis(format='$,.0f')),
            color='Category',
            tooltip=['Category', alt.Tooltip('Cost', format='$,.0f')]
        )
        st.altair_chart(bar, use_container_width=True)

st.divider()
st.markdown("#### ⚙️ Print Job Statistics")

if is_metric:
    weight_display = f"{weight_tons * (1/TONNE_TO_TON):.1f} Tonnes"
    dist_display = f"{(total_path_length_ft * MM_TO_FT)/1000 * 304.8:.2f} km" 
else:
    weight_display = f"{weight_tons:.1f} Tons"
    dist_display = f"{total_path_length_ft/5280:.2f} Miles"

p1, p2, p3, p4 = st.columns(4)
p1.metric("Print Time", f"{real_print_time_hr:.1f} Hours")
p2.metric("Material Weight", weight_display)
p3.metric("Nozzle Travel Length", dist_display)
p4.metric("Print Layers", f"{int(total_layers)}")

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: grey; font-size: 12px;'>
        Built by <b>Dan Kositzke</b> | <a href='mailto:dankositzke2050@gmail.com'>dankositzke2050@gmail.com</a>
    </div>
    """,
    unsafe_allow_html=True
)