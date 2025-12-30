import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import math

# ---------------------------------------------------------
# 0. PAGE CONFIG (must be first Streamlit command)
# ---------------------------------------------------------
st.set_page_config(page_title="3DCP Wall Package Cost Estimator", page_icon="🏗️", layout="wide")

# ---------------------------------------------------------
# 1. CONSTANTS & CONVERSIONS
# ---------------------------------------------------------
SQ_M_TO_SQ_FT = 10.7639104
TONNE_TO_TON = 1.10231
KG_M3_TO_LBS_FT3 = 0.06242796
MM_TO_FT = 0.00328084
MM_TO_INCH = 0.0393701
M_TO_FT = 3.28084
FT_TO_M = 0.3048
SHIFT_HOURS = 8

# ---------------------------------------------------------
# 2. DATABASE
# ---------------------------------------------------------
PRINTERS = {
    "COBOD BOD2": {
        "price": 580000, "speed_mm_s": 250, "setup_days": 1.0, "teardown_days": 1.0,
        "crew_size": 3, "efficiency": 0.65, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "COBOD BOD3": {
        "price": 1000000, "speed_mm_s": 250, "setup_days": 1.0, "teardown_days": 1.0,
        "crew_size": 3, "efficiency": 0.70, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "CyBe RC (Robot Crawler)": {
        "price": 230000, "speed_mm_s": 250, "setup_days": 0.5, "teardown_days": 0.5,
        "crew_size": 2, "efficiency": 0.55, "bead_width_mm": 40, "layer_height_mm": 15
    },
    "MudBots (25x25 Model)": {
        "price": 285000, "speed_mm_s": 144, "setup_days": 1.0, "teardown_days": 1.0,
        "crew_size": 3, "efficiency": 0.50, "bead_width_mm": 40, "layer_height_mm": 20
    },
    "RIC Technology RIC-M1": {
        "price": 250000, "speed_mm_s": 150, "setup_days": 0.2, "teardown_days": 0.2,
        "crew_size": 2, "efficiency": 0.55, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "X-Hab 3D MX3DP": {
        "price": 450000, "speed_mm_s": 250, "setup_days": 0.2, "teardown_days": 0.2,
        "crew_size": 3, "efficiency": 0.55, "bead_width_mm": 45, "layer_height_mm": 20
    },
    "Coral 3DCP (Mobile Unit)": {
        "price": 350000, "speed_mm_s": 330, "setup_days": 0.2, "teardown_days": 0.2,
        "crew_size": 2, "efficiency": 0.55, "bead_width_mm": 60, "layer_height_mm": 20
    },
    "Alquist 3D A1X": {
        "price": 450000, "speed_mm_s": 200, "setup_days": 1.0, "teardown_days": 1.0,
        "crew_size": 3, "efficiency": 0.60, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "SQ4D ARCS": {
        "price": 400000, "speed_mm_s": 250, "setup_days": 2.0, "teardown_days": 2.0,
        "crew_size": 3, "efficiency": 0.65, "bead_width_mm": 80, "layer_height_mm": 25
    }
}

MATERIALS = {
    "Local Concrete + D.fab": {"type": "Admix", "price_ton": 70, "density_lbs_ft3": 145, "waste_pct": 0.10},
    "CyBe Mortar": {"type": "Premix", "price_ton": 420, "density_lbs_ft3": 131, "waste_pct": 0.05},
    "CyBe Power Pack": {"type": "Premix", "price_ton": 150, "density_lbs_ft3": 145, "waste_pct": 0.05},
    "Sika Sikacrete®-733 3D": {"type": "Premix", "price_ton": 450, "density_lbs_ft3": 137, "waste_pct": 0.03},
    "Heidelberg evoBuild / i.tech": {"type": "Premix", "price_ton": 500, "density_lbs_ft3": 134, "waste_pct": 0.04},
    "Eco Material PozzoCEM": {"type": "Green-Mix", "price_ton": 200, "density_lbs_ft3": 137, "waste_pct": 0.08},
    "Eco Material PozzoSlag": {"type": "Green-Mix", "price_ton": 125, "density_lbs_ft3": 137, "waste_pct": 0.08},
    "Local Concrete + Coral Admix": {"type": "Admix", "price_ton": 80, "density_lbs_ft3": 145, "waste_pct": 0.10},
    "Local Concrete + SQ4D Admix": {"type": "Admix", "price_ton": 150, "density_lbs_ft3": 145, "waste_pct": 0.10},
}

# ---------------------------------------------------------
# 3. HELPERS
# ---------------------------------------------------------
def get_printer_specs(name):
    return PRINTERS.get(name, PRINTERS["COBOD BOD2"])

def get_material_specs(name):
    return MATERIALS.get(name, MATERIALS["Local Concrete + D.fab"])

def fmt_money(x):
    return f"${x:,.0f}"

def fmt_signed_money(x):
    sign = "+" if x >= 0 else "-"
    return f"{sign}${abs(x):,.0f}"

def safe_div(a, b):
    return a / b if b not in (0, 0.0) else 0.0

def round_to_nearest_thousand(x: float) -> int:
    x = float(max(0.0, x))
    return int(math.floor((x + 500.0) / 1000.0) * 1000.0)

def calc_monthly_payment(principal: float, annual_rate: float = 0.10, months: int = 60) -> float:
    principal = float(max(0.0, principal))
    months = int(max(1, months))
    r = float(annual_rate) / 12.0
    if r <= 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** (-months))

def build_pnl_df(res, sale_price, sga_per_home):
    """
    Two-column P&L (Per Home):
    - Cash P&L: ignores D&A (pure operating cash economics, not financing)
    - Accounting P&L: includes D&A allocation (accrual economics)
    """
    cash_cogs = float(res.get("cash_cogs_total", res.get("cash_cost_total", 0.0)))
    da = float(res.get("machine_cost", 0.0))  # per-home D&A allocation (non-cash)

    gross_profit = float(sale_price) - cash_cogs
    ebitda = gross_profit - float(sga_per_home)

    cash_ebit = ebitda
    accrual_ebit = ebitda - da

    rows = [
        {"Line Item": "Revenue", "Cash P&L": sale_price, "Accounting P&L": sale_price},

        {"Line Item": "COGS — Material", "Cash P&L": res.get("mat_cost", 0.0), "Accounting P&L": res.get("mat_cost", 0.0)},
        {"Line Item": "COGS — Labor", "Cash P&L": res.get("labor_cost", 0.0), "Accounting P&L": res.get("labor_cost", 0.0)},
        {"Line Item": "COGS — Logistics", "Cash P&L": res.get("logistics_cost", 0.0), "Accounting P&L": res.get("logistics_cost", 0.0)},
        {"Line Item": "COGS — Integration", "Cash P&L": res.get("bos_cost", 0.0), "Accounting P&L": res.get("bos_cost", 0.0)},
        {"Line Item": "Total COGS (Cash)", "Cash P&L": cash_cogs, "Accounting P&L": cash_cogs},

        {"Line Item": "Gross Profit", "Cash P&L": gross_profit, "Accounting P&L": gross_profit},

        {"Line Item": "SG&A / Overhead", "Cash P&L": sga_per_home, "Accounting P&L": sga_per_home},
        {"Line Item": "EBITDA", "Cash P&L": ebitda, "Accounting P&L": ebitda},

        {"Line Item": "Depreciation/Amortization (Printer)", "Cash P&L": 0.0, "Accounting P&L": da},
        {"Line Item": "EBIT (Operating Profit)", "Cash P&L": cash_ebit, "Accounting P&L": accrual_ebit},
    ]

    df = pd.DataFrame(rows).copy()
    for col in ["Cash P&L", "Accounting P&L"]:
        df[col] = df[col].astype(float)

    if sale_price > 0:
        metrics = [
            {"Metric": "EBITDA Margin", "Cash": ebitda / sale_price, "Accounting": ebitda / sale_price},
            {"Metric": "EBIT Margin", "Cash": cash_ebit / sale_price, "Accounting": accrual_ebit / sale_price},
            {"Metric": "Cash COGS % of Revenue", "Cash": cash_cogs / sale_price, "Accounting": cash_cogs / sale_price},
        ]
    else:
        metrics = [
            {"Metric": "EBITDA Margin", "Cash": 0.0, "Accounting": 0.0},
            {"Metric": "EBIT Margin", "Cash": 0.0, "Accounting": 0.0},
            {"Metric": "Cash COGS % of Revenue", "Cash": 0.0, "Accounting": 0.0},
        ]

    df_m = pd.DataFrame(metrics)
    return df, df_m

# ---------------------------------------------------------
# 3.5. UNIT-TOGGLE STABILITY (NO ROUND-TRIP DRIFT)
# ---------------------------------------------------------
def _ensure_state(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

def _set_ui_from_base(is_metric: bool):
    """
    Canonical "base_*" values are stored in fixed internal units:
      - base_sq_ft_home           : ft²
      - base_wall_height_ft       : ft
      - base_layer_h_mm           : mm
      - base_bead_w_mm            : mm
      - base_mat_price_ton        : $/US short ton
      - base_density_lbs_ft3      : lbs/ft³
      - base_rebar_cost_ft        : $/linear ft
      - base_misc_bos_sqft        : $/ft² wall
    UI widgets are set from these bases so toggling units never changes the underlying model.
    """
    st.session_state["ui_home_area"] = (
        st.session_state["base_sq_ft_home"] / SQ_M_TO_SQ_FT if is_metric else st.session_state["base_sq_ft_home"]
    )
    st.session_state["ui_wall_height"] = (
        st.session_state["base_wall_height_ft"] * FT_TO_M if is_metric else st.session_state["base_wall_height_ft"]
    )
    st.session_state["ui_layer_h"] = (
        st.session_state["base_layer_h_mm"] if is_metric else st.session_state["base_layer_h_mm"] * MM_TO_INCH
    )
    st.session_state["ui_bead_w"] = (
        st.session_state["base_bead_w_mm"] if is_metric else st.session_state["base_bead_w_mm"] * MM_TO_INCH
    )
    st.session_state["ui_mat_price"] = (
        st.session_state["base_mat_price_ton"] * TONNE_TO_TON if is_metric else st.session_state["base_mat_price_ton"]
    )
    st.session_state["ui_density"] = (
        st.session_state["base_density_lbs_ft3"] / KG_M3_TO_LBS_FT3 if is_metric else st.session_state["base_density_lbs_ft3"]
    )
    st.session_state["ui_rebar_cost"] = (
        st.session_state["base_rebar_cost_ft"] * M_TO_FT if is_metric else st.session_state["base_rebar_cost_ft"]
    )
    st.session_state["ui_misc_bos"] = (
        st.session_state["base_misc_bos_sqft"] * SQ_M_TO_SQ_FT if is_metric else st.session_state["base_misc_bos_sqft"]
    )

# ---------------------------------------------------------
# 4. THE PHYSICS ENGINE & AUDITOR
# ---------------------------------------------------------
def calculate_costs(p, is_metric: bool):
    audit = {}
    warnings = []

    safe_eff = max(0.01, float(p['efficiency']))

    if safe_eff > 0.90:
        warnings.append("⚠️ Efficiency > 90% is extremely aggressive for construction.")
    if p['print_speed_mm_s'] > 300 and float(p['layer_h_mm']) > 25:
        warnings.append("⚠️ High Speed + High Layer Height may cause slump/collapse.")

    # A. Geometry
    linear_wall_ft = float(p['sq_ft_home']) * float(p['wall_density'])
    wall_sq_ft = linear_wall_ft * float(p['wall_height_ft'])
    wall_height_mm = float(p['wall_height_ft']) * 304.8

    layer_h_mm_safe = max(0.5, float(p['layer_h_mm']))
    bead_w_mm_safe = max(1.0, float(p['bead_w_mm']))

    total_layers = wall_height_mm / layer_h_mm_safe
    total_path_length_ft = linear_wall_ft * total_layers * float(p['passes_per_layer'])

    audit['Geometry'] = (
        f"Wall Length: {linear_wall_ft:.0f} ft | Wall Area: {wall_sq_ft:,.0f} ft² | "
        f"Layers: {int(total_layers)} | Path: {total_path_length_ft:,.0f} ft"
    )

    # B. Time (speed + efficiency)
    avg_speed_mm_s = max(1.0, float(p['print_speed_mm_s']))

    speed_ft_hr = avg_speed_mm_s * 11.811
    theoretical_time_hr = total_path_length_ft / speed_ft_hr
    real_print_time_hr = theoretical_time_hr / safe_eff

    print_days = real_print_time_hr / SHIFT_HOURS
    total_project_days = (float(p['setup_days']) + float(p['teardown_days'])) * float(p['moves_count']) + (print_days * float(p['num_homes']))
    days_per_home = total_project_days / float(p['num_homes'])

    project_months = max(1, int(math.ceil(total_project_days / 30.0)))

    audit['Time'] = (
        f"Speed: {avg_speed_mm_s:.0f} mm/s | Print Days: {print_days:.1f} | "
        f"Moves: {int(p['moves_count'])} | Project: {total_project_days:.1f} days (~{project_months} mo)"
    )

    # C. Material
    vol_cu_ft = total_path_length_ft * (layer_h_mm_safe * MM_TO_FT) * (bead_w_mm_safe * MM_TO_FT)
    weight_lbs = vol_cu_ft * float(p['final_density_lbs_ft3'])
    weight_tons = weight_lbs / 2000.0
    total_mat_cost_per_home = weight_tons * float(p['mat_price_ton']) * (1 + float(p['waste_pct']))

    flow_rate_l_min = (avg_speed_mm_s * bead_w_mm_safe * layer_h_mm_safe * 60) / 1_000_000.0
    if flow_rate_l_min > 30:
        warnings.append(f"⚠️ Flow Rate {flow_rate_l_min:.1f} L/min exceeds typical pump capacity (20-30 L/min).")

    # D. Labor
    setup_hrs_per_move = float(p['setup_days']) * SHIFT_HOURS
    teardown_hrs_per_move = float(p['teardown_days']) * SHIFT_HOURS

    labor_setup_per_move = (setup_hrs_per_move + teardown_hrs_per_move) * float(p['crew_size']) * float(p['labor_rate'])
    labor_print_per_home = real_print_time_hr * float(p['crew_size']) * float(p['labor_rate'])

    total_setup_labor_project = labor_setup_per_move * float(p['moves_count'])
    total_print_labor_project = labor_print_per_home * float(p['num_homes'])
    total_labor_cost_per_home = (total_setup_labor_project + total_print_labor_project) / float(p['num_homes'])

    # E. Logistics (cash)
    logistics_cost_per_move = (float(p['setup_days']) + float(p['teardown_days'])) * float(p['crane_rate'])
    total_logistics_cost = logistics_cost_per_move * float(p['moves_count'])
    logistics_cost_per_home = total_logistics_cost / float(p['num_homes'])

    # F. BOS (cash)
    rebar_total = linear_wall_ft * float(p['rebar_cost_ft'])
    misc_bos_total = wall_sq_ft * float(p['misc_bos_sqft'])
    total_bos_cost = rebar_total + misc_bos_total

    # ---------------------------------------------------------
    # PRINTER ACQUISITION LOGIC
    # ---------------------------------------------------------
    printer_upfront_pct = float(p.get("printer_upfront_pct", 0.0))
    printer_upfront_cash = float(p['printer_price']) * printer_upfront_pct

    printer_monthly_payment = float(p.get("printer_monthly_payment", 0.0))
    printer_acq_type = p.get("printer_acquisition_type", "Cash (Own)")

    own_printer = (printer_acq_type != "Lease/Rent (Expense)")

    # Non-cash D&A only if owned
    if own_printer:
        machine_cost_per_year = (float(p['printer_price']) * (1 - float(p['residual_value_pct']))) / float(p['depreciation_years'])
        machine_cost_per_home = machine_cost_per_year / float(p['est_prints_per_year'])
    else:
        machine_cost_per_home = 0.0

    # Lease/Rent: payment is operating expense (cash COGS)
    printer_lease_expense_project = 0.0
    printer_lease_expense_per_home = 0.0
    if (not own_printer) and printer_monthly_payment > 0:
        printer_lease_expense_project = printer_monthly_payment * project_months
        printer_lease_expense_per_home = printer_lease_expense_project / float(p['num_homes'])

    # Finance (Own): payment is cash flow, not P&L expense
    printer_debt_service_project = 0.0
    printer_debt_service_per_home = 0.0
    if own_printer and printer_acq_type == "Finance (Own)" and printer_monthly_payment > 0 and printer_upfront_pct < 1.0:
        printer_debt_service_project = printer_monthly_payment * project_months
        printer_debt_service_per_home = printer_debt_service_project / float(p['num_homes'])

    # CASH vs ACCRUAL COSTS
    cash_cogs_core = total_mat_cost_per_home + total_labor_cost_per_home + logistics_cost_per_home + total_bos_cost
    cash_cogs_total = cash_cogs_core + printer_lease_expense_per_home  # lease adds to COGS

    grand_total = cash_cogs_total + (machine_cost_per_home if own_printer else 0.0)

    # Upfront capital required (pre-revenue proxy)
    first_payment_cash = printer_monthly_payment if (printer_upfront_pct < 1.0 and printer_monthly_payment > 0) else 0.0
    cash_required = (
        printer_upfront_cash
        + logistics_cost_per_move
        + labor_setup_per_move
        + labor_print_per_home
        + total_mat_cost_per_home
        + first_payment_cash
    )

    # Unit cost (per floor area)
    if is_metric:
        area_m2 = float(p['sq_ft_home']) / SQ_M_TO_SQ_FT
        cost_per_area = grand_total / area_m2
        home_area = area_m2
    else:
        cost_per_area = grand_total / float(p['sq_ft_home'])
        home_area = float(p['sq_ft_home'])

    return {
        "grand_total": grand_total,
        "cash_cost_total": cash_cogs_total,
        "cash_cogs_total": cash_cogs_total,
        "cash_cogs_core": cash_cogs_core,

        "mat_cost": total_mat_cost_per_home,
        "labor_cost": total_labor_cost_per_home,
        "logistics_cost": logistics_cost_per_home,
        "bos_cost": total_bos_cost,
        "machine_cost": machine_cost_per_home,

        "printer_upfront_cash": printer_upfront_cash,
        "printer_acquisition_type": printer_acq_type,
        "printer_monthly_payment": printer_monthly_payment,
        "printer_lease_expense_per_home": printer_lease_expense_per_home,
        "printer_debt_service_per_home": printer_debt_service_per_home,
        "project_months": project_months,

        "real_print_time_hr": real_print_time_hr,
        "weight_tons": weight_tons,
        "total_path_length_ft": total_path_length_ft,
        "total_layers": total_layers,
        "avg_speed_mm_s": avg_speed_mm_s,
        "days_per_home": days_per_home,
        "total_project_days": total_project_days,
        "cash_required": cash_required,
        "cost_per_area": cost_per_area,
        "flow_rate": flow_rate_l_min,

        "audit": audit,
        "warnings": warnings,

        "linear_wall_ft": linear_wall_ft,
        "wall_sq_ft": wall_sq_ft,
        "home_area": home_area
    }

# ---------------------------------------------------------
# 6. HEADER
# ---------------------------------------------------------
st.title("🏗️ 3DCP Wall Package Cost Estimator")
st.markdown("### Compare project economics for printers and materials")
st.divider()

# ---------------------------------------------------------
# 7. MAIN CONTROL PANEL (Project)
# ---------------------------------------------------------
with st.container(border=True):
    st.markdown("#### Project Configuration")

    unit_col, _ = st.columns([1, 2])
    with unit_col:
        unit_system = st.radio(
            "Unit System:",
            ["Imperial (US)", "Metric (EU)"],
            horizontal=True,
            key="ui_unit_system"
        )

    is_metric = unit_system == "Metric (EU)"
    area_unit = "$/m²" if is_metric else "$/sqft"

    c1, c2, c3, c4 = st.columns(4)

    printer_names = list(PRINTERS.keys())
    material_names = list(MATERIALS.keys())

    try:
        dfab_index = material_names.index("Local Concrete + D.fab")
    except ValueError:
        dfab_index = 0

    with c1:
        selected_printer = st.selectbox("Select Printer", printer_names, index=0, key="ui_selected_printer")
    with c2:
        selected_material = st.selectbox("Select Material Strategy", material_names, index=dfab_index, key="ui_selected_material")
    with c3:
        num_homes = st.number_input("Number of Homes In Project", min_value=1, value=6, step=1, key="ui_num_homes")

    # --- Base defaults (canonical internal units) ---
    printer_defaults = PRINTERS[selected_printer]
    mat_defaults = MATERIALS[selected_material]

    refresh_ui = False

    # Initialize base state once (or when printer/material changes)
    if "base_initialized" not in st.session_state:
        refresh_ui = True

    # Core base defaults (only set if missing)
    _ensure_state("base_sq_ft_home", 1500.0)
    _ensure_state("base_wall_height_ft", 9.0)
    _ensure_state("base_rebar_cost_ft", 2.0)
    _ensure_state("base_misc_bos_sqft", 2.25)

    # Printer-dependent bases
    if st.session_state.get("_prev_selected_printer") != selected_printer or "base_layer_h_mm" not in st.session_state:
        st.session_state["_prev_selected_printer"] = selected_printer
        st.session_state["base_layer_h_mm"] = float(printer_defaults["layer_height_mm"])
        st.session_state["base_bead_w_mm"] = float(printer_defaults["bead_width_mm"])
        refresh_ui = True

    # Material-dependent bases
    if st.session_state.get("_prev_selected_material") != selected_material or "base_mat_price_ton" not in st.session_state:
        st.session_state["_prev_selected_material"] = selected_material
        st.session_state["base_mat_price_ton"] = float(mat_defaults["price_ton"])
        st.session_state["base_density_lbs_ft3"] = float(mat_defaults["density_lbs_ft3"])
        refresh_ui = True

    # Unit toggle: refresh UI widgets from base (do NOT change base values)
    if st.session_state.get("_prev_is_metric") is None:
        st.session_state["_prev_is_metric"] = is_metric
        refresh_ui = True
    elif st.session_state.get("_prev_is_metric") != is_metric:
        st.session_state["_prev_is_metric"] = is_metric
        refresh_ui = True

    if refresh_ui:
        _set_ui_from_base(is_metric)
        st.session_state["base_initialized"] = True

    with c4:
        if is_metric:
            st.number_input(
                "Avg. Floor Area (m²)",
                min_value=1.0,
                step=1.0,
                format="%.2f",
                key="ui_home_area"
            )
        else:
            st.number_input(
                "Avg. Floor Area (ft²)",
                min_value=1.0,
                step=10.0,
                format="%.0f",
                key="ui_home_area"
            )

        # Update canonical base from UI (only this line connects UI↔model)
        if is_metric:
            st.session_state["base_sq_ft_home"] = float(st.session_state["ui_home_area"]) * SQ_M_TO_SQ_FT
        else:
            st.session_state["base_sq_ft_home"] = float(st.session_state["ui_home_area"])

# ---------------------------------------------------------
# 9. ADVANCED OVERRIDES
# ---------------------------------------------------------
st.write("")

with st.expander("🛠️ Advanced Assumptions (Click to Edit)"):
    tab_fin, tab_geo, tab_ops, tab_bos = st.tabs(
        ["💵 Financials", "📐 Geometry & Print", "⚙️ Operations", "🧱 Integration"]
    )

    with tab_fin:
        f1, f2, f3 = st.columns(3)

        with f1:
            st.markdown("**Material Costs**")

            if "ui_mat_price" not in st.session_state:
                _set_ui_from_base(is_metric)

            if is_metric:
                st.number_input("Material Price ($/tonne)", min_value=0.0, step=10.0, format="%.2f", key="ui_mat_price")
                st.session_state["base_mat_price_ton"] = float(st.session_state["ui_mat_price"]) * (1.0 / TONNE_TO_TON)
            else:
                st.number_input("Material Price ($/ton)", min_value=0.0, step=10.0, format="%.2f", key="ui_mat_price")
                st.session_state["base_mat_price_ton"] = float(st.session_state["ui_mat_price"])

            _ensure_state("ui_waste_pct", float(mat_defaults["waste_pct"] * 100.0))
            st.number_input("Material Waste %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f", key="ui_waste_pct")
            waste_pct = float(st.session_state["ui_waste_pct"]) / 100.0

        with f2:
            st.markdown("**Labor, Logistics & Overhead**")
            _ensure_state("ui_labor_rate", 40.0)
            _ensure_state("ui_crane_rate", 1500.0)
            _ensure_state("ui_sga_per_home", 0.0)

            st.number_input("Crew Labor Rate ($/hr)", min_value=0.0, step=5.0, key="ui_labor_rate")
            st.number_input("Crane Rate ($/day)", min_value=0.0, step=100.0, key="ui_crane_rate")
            st.number_input(
                "SG&A / Overhead ($/home)",
                min_value=0.0,
                step=500.0,
                key="ui_sga_per_home",
                help="Optional overhead per home (supervision, admin, insurance, office, sales support, etc.)."
            )

            labor_rate = float(st.session_state["ui_labor_rate"])
            crane_rate = float(st.session_state["ui_crane_rate"])
            sga_per_home = float(st.session_state["ui_sga_per_home"])

        with f3:
            st.markdown("**Printer (Asset + Cash Structure)**")

            left, right = st.columns([1, 1], gap="large")

            with left:
                _ensure_state("ui_printer_price", float(printer_defaults["price"]))
                _ensure_state("ui_depreciation_years", 5)
                _ensure_state("ui_residual_val", 20)
                _ensure_state("ui_est_prints_per_year", 12)

                st.number_input("Printer Hardware Cost ($)", min_value=0.0, step=5000.0, key="ui_printer_price")
                st.number_input("Amortization Period (Yrs)", min_value=1, step=1, key="ui_depreciation_years")
                st.number_input("Residual Value (%)", min_value=0, max_value=100, step=5, key="ui_residual_val")
                st.number_input("Annual Utilization (Homes/Yr)", min_value=1, step=1, key="ui_est_prints_per_year")

                printer_price = float(st.session_state["ui_printer_price"])
                depreciation_years = int(st.session_state["ui_depreciation_years"])
                residual_value_pct = float(st.session_state["ui_residual_val"]) / 100.0
                est_prints_per_year = int(st.session_state["ui_est_prints_per_year"])

            with right:
                DEFAULT_UPFRONT_PCT = 20
                DEFAULT_APR = 0.10
                term_months = max(1, int(depreciation_years * 12))

                _ensure_state("ui_printer_upfront_pct", DEFAULT_UPFRONT_PCT)
                st.number_input(
                    "Upfront Printer Cash (%)",
                    min_value=0,
                    max_value=100,
                    step=5,
                    key="ui_printer_upfront_pct",
                    help="Default 20%. If < 100%, monthly payment auto-fills using 10% APR and term = amortization years."
                )
                printer_upfront_pct = float(st.session_state["ui_printer_upfront_pct"]) / 100.0

                remaining_principal = printer_price * (1 - printer_upfront_pct)
                suggested_payment = calc_monthly_payment(
                    principal=remaining_principal,
                    annual_rate=DEFAULT_APR,
                    months=term_months
                )

                printer_acquisition_type = "Cash (Own)"
                printer_monthly_payment = 0.0

                if st.session_state["ui_printer_upfront_pct"] < 100:
                    _ensure_state("ui_printer_acquisition_type", "Finance (Own)")
                    printer_acquisition_type = st.radio(
                        "Printer acquisition type",
                        ["Finance (Own)", "Lease/Rent (Expense)"],
                        horizontal=True,
                        key="ui_printer_acquisition_type",
                        help=(
                            "Finance (Own): Depr/Amort applies; payments shown as cash flow. "
                            "Lease/Rent: payment treated as operating expense (COGS); no Depr/Amort."
                        )
                    )

                    _ensure_state("ui_auto_calc_payment", True)
                    auto_calc = st.checkbox(
                        "Auto-calc monthly payment (10% APR)",
                        value=bool(st.session_state["ui_auto_calc_payment"]),
                        key="ui_auto_calc_payment",
                        help=f"Uses remaining balance and term = {term_months} months."
                    )

                    _ensure_state("ui_printer_monthly_payment", float(round(suggested_payment, 0)))

                    if auto_calc:
                        # keep UI in sync with the suggestion when auto-calc is on
                        st.session_state["ui_printer_monthly_payment"] = float(round(suggested_payment, 0))

                    st.number_input(
                        "Monthly Printer Payment ($/month)",
                        min_value=0.0,
                        step=500.0,
                        key="ui_printer_monthly_payment",
                        disabled=auto_calc
                    )
                    printer_monthly_payment = float(st.session_state["ui_printer_monthly_payment"])

                    st.caption(
                        f"Default calc: 10% APR, {term_months} months, remaining balance = {fmt_money(remaining_principal)}"
                    )
                else:
                    printer_acquisition_type = "Cash (Own)"
                    printer_monthly_payment = 0.0

    with tab_geo:
        g1, g2 = st.columns(2)

        with g1:
            st.markdown("**Wall Dimensions**")
            _ensure_state("ui_wall_density", 0.20)
            st.number_input(
                "Wall Density Factor",
                min_value=0.0,
                format="%.2f",
                key="ui_wall_density",
                help=(
                    "Linear wall ft per sq ft of floor. "
                    "Higher = more rooms and corners per area. "
                    "Example: a 1,500 ft² home at 0.20 ⇒ ~300 linear ft of wall."
                )
            )

            if "ui_wall_height" not in st.session_state:
                _set_ui_from_base(is_metric)

            if is_metric:
                st.number_input("Wall Height (m)", min_value=0.1, step=0.05, format="%.3f", key="ui_wall_height")
                st.session_state["base_wall_height_ft"] = float(st.session_state["ui_wall_height"]) * M_TO_FT
            else:
                st.number_input("Wall Height (ft)", min_value=0.1, step=0.25, format="%.2f", key="ui_wall_height")
                st.session_state["base_wall_height_ft"] = float(st.session_state["ui_wall_height"])

            wall_density = float(st.session_state["ui_wall_density"])
            wall_height_ft = float(st.session_state["base_wall_height_ft"])

        with g2:
            st.markdown("**Print Resolution**")

            if "ui_layer_h" not in st.session_state or "ui_bead_w" not in st.session_state:
                _set_ui_from_base(is_metric)

            if is_metric:
                st.number_input("Layer Height (mm)", min_value=1.0, step=1.0, format="%.2f", key="ui_layer_h")
                st.number_input("Bead Width (mm)", min_value=1.0, step=1.0, format="%.2f", key="ui_bead_w")
                st.session_state["base_layer_h_mm"] = float(st.session_state["ui_layer_h"])
                st.session_state["base_bead_w_mm"] = float(st.session_state["ui_bead_w"])
            else:
                st.number_input("Layer Height (in)", min_value=0.001, step=0.001, format="%.3f", key="ui_layer_h")
                st.number_input("Bead Width (in)", min_value=0.001, step=0.001, format="%.3f", key="ui_bead_w")
                st.session_state["base_layer_h_mm"] = float(st.session_state["ui_layer_h"]) * (1.0 / MM_TO_INCH)
                st.session_state["base_bead_w_mm"] = float(st.session_state["ui_bead_w"]) * (1.0 / MM_TO_INCH)

            _ensure_state("ui_passes_per_layer", 2)
            st.number_input(
                "Passes per Layer",
                min_value=1,
                max_value=4,
                step=1,
                key="ui_passes_per_layer",
                help=(
                    "How many parallel beads are printed each layer. "
                    "Default = 2 (double-wall / cavity wall), often used to allow insulation + MEP chase in the middle. "
                    "1 = single-wall."
                )
            )

            layer_h_mm = float(st.session_state["base_layer_h_mm"])
            bead_w_mm = float(st.session_state["base_bead_w_mm"])
            passes_per_layer = int(st.session_state["ui_passes_per_layer"])

    with tab_ops:
        o1, o2, o3 = st.columns(3)

        with o1:
            st.markdown("**Speed & Efficiency**")
            _ensure_state("ui_print_speed_mm_s", int(printer_defaults["speed_mm_s"]))
            _ensure_state("ui_efficiency_pct", int(printer_defaults["efficiency"] * 100))

            st.number_input("Max Print Speed (mm/s)", min_value=10, step=10, key="ui_print_speed_mm_s")
            st.number_input(
                "Machine Efficiency %",
                min_value=1,
                max_value=100,
                step=5,
                key="ui_efficiency_pct",
                help=(
                    "% of the shift where the nozzle is actually extruding. "
                    "Captures downtime (refills, cleaning, troubleshooting, pauses, minor maintenance) and repositioning during the print (for non-gantry systems)."
                )
            )

            print_speed_mm_s = int(st.session_state["ui_print_speed_mm_s"])
            efficiency = float(st.session_state["ui_efficiency_pct"]) / 100.0

        with o2:
            st.markdown("**Site Crew**")
            _ensure_state("ui_crew_size", int(printer_defaults["crew_size"]))
            st.number_input("Crew Size (People)", min_value=1, step=1, key="ui_crew_size")

            moves_default = max(1, math.ceil(int(num_homes) / 2))
            _ensure_state("ui_moves_count", moves_default)
            st.number_input(
                "Printer Moves (Crane Lifts)",
                min_value=1,
                step=1,
                key="ui_moves_count",
                help=(
                    "How many times the printer must be disassembled and moved via crane/rigging. "
                    "Default: ~1 move per 2 homes."
                )
            )

            crew_size = int(st.session_state["ui_crew_size"])
            moves_count = int(st.session_state["ui_moves_count"])

        with o3:
            st.markdown("**Material Params**")

            if "ui_density" not in st.session_state:
                _set_ui_from_base(is_metric)

            if is_metric:
                st.number_input("Dry Density (kg/m³)", min_value=1.0, step=10.0, format="%.1f", key="ui_density")
                st.session_state["base_density_lbs_ft3"] = float(st.session_state["ui_density"]) * KG_M3_TO_LBS_FT3
            else:
                st.number_input("Dry Density (lbs/ft³)", min_value=1.0, step=1.0, format="%.1f", key="ui_density")
                st.session_state["base_density_lbs_ft3"] = float(st.session_state["ui_density"])

            final_density_lbs_ft3 = float(st.session_state["base_density_lbs_ft3"])

    with tab_bos:
        st.markdown("**Mobilization**")
        b1, b2 = st.columns(2)

        _ensure_state("ui_setup_days", float(printer_defaults["setup_days"]))
        _ensure_state("ui_teardown_days", float(printer_defaults["teardown_days"]))

        with b1:
            st.number_input("Setup Days (per move)", min_value=0.0, step=0.5, key="ui_setup_days")
        with b2:
            st.number_input("Teardown Days (per move)", min_value=0.0, step=0.5, key="ui_teardown_days")

        setup_days = float(st.session_state["ui_setup_days"])
        teardown_days = float(st.session_state["ui_teardown_days"])

        st.divider()

        b3, b4 = st.columns(2)

        with b3:
            st.markdown("**Reinforcement (Rebar)**")
            if "ui_rebar_cost" not in st.session_state:
                _set_ui_from_base(is_metric)

            if is_metric:
                st.number_input(
                    "Rebar Cost ($/linear meter)",
                    min_value=0.0,
                    step=0.25,
                    format="%.2f",
                    key="ui_rebar_cost",
                    help="Reinforcement required to make the printed wall structural."
                )
                st.session_state["base_rebar_cost_ft"] = float(st.session_state["ui_rebar_cost"]) * (1.0 / M_TO_FT)
            else:
                st.number_input(
                    "Rebar Cost ($/linear foot)",
                    min_value=0.0,
                    step=0.25,
                    format="%.2f",
                    key="ui_rebar_cost",
                    help="Reinforcement required to make the printed wall structural."
                )
                st.session_state["base_rebar_cost_ft"] = float(st.session_state["ui_rebar_cost"])

            rebar_cost_ft = float(st.session_state["base_rebar_cost_ft"])

        with b4:
            st.markdown("**Insulation & Lintels**")
            if "ui_misc_bos" not in st.session_state:
                _set_ui_from_base(is_metric)

            if is_metric:
                st.number_input(
                    "Misc Integration ($/m² of wall)",
                    min_value=0.0,
                    step=0.25,
                    format="%.2f",
                    key="ui_misc_bos",
                    help="Other integration items (lintels, bucks, embeds, insulation fill, patching, etc.)."
                )
                st.session_state["base_misc_bos_sqft"] = float(st.session_state["ui_misc_bos"]) * (1.0 / SQ_M_TO_SQ_FT)
            else:
                st.number_input(
                    "Misc Integration ($/ft² of wall)",
                    min_value=0.0,
                    step=0.25,
                    format="%.2f",
                    key="ui_misc_bos",
                    help="Other integration items (lintels, bucks, embeds, insulation fill, patching, etc.)."
                )
                st.session_state["base_misc_bos_sqft"] = float(st.session_state["ui_misc_bos"])

            misc_bos_sqft = float(st.session_state["base_misc_bos_sqft"])

# ---------------------------------------------------------
# 10. SCENARIO INPUTS (CANONICAL BASES FEED THE MODEL)
# ---------------------------------------------------------
sq_ft_home = float(st.session_state["base_sq_ft_home"])
mat_price_ton = float(st.session_state["base_mat_price_ton"])

inputs_a = {
    'sq_ft_home': sq_ft_home,
    'wall_density': float(st.session_state.get("ui_wall_density", 0.20)),
    'wall_height_ft': float(st.session_state["base_wall_height_ft"]),

    'layer_h_mm': float(st.session_state["base_layer_h_mm"]),
    'passes_per_layer': int(st.session_state.get("ui_passes_per_layer", 2)),
    'print_speed_mm_s': int(st.session_state.get("ui_print_speed_mm_s", int(printer_defaults["speed_mm_s"]))),

    'efficiency': float(st.session_state.get("ui_efficiency_pct", int(printer_defaults["efficiency"] * 100))) / 100.0,
    'bead_w_mm': float(st.session_state["base_bead_w_mm"]),
    'final_density_lbs_ft3': float(st.session_state["base_density_lbs_ft3"]),

    'mat_price_ton': mat_price_ton,
    'waste_pct': float(st.session_state.get("ui_waste_pct", float(mat_defaults["waste_pct"] * 100.0))) / 100.0,

    'setup_days': float(st.session_state.get("ui_setup_days", float(printer_defaults["setup_days"]))),
    'teardown_days': float(st.session_state.get("ui_teardown_days", float(printer_defaults["teardown_days"]))),
    'moves_count': int(st.session_state.get("ui_moves_count", max(1, math.ceil(int(num_homes) / 2)))),

    'crew_size': int(st.session_state.get("ui_crew_size", int(printer_defaults["crew_size"]))),
    'labor_rate': float(st.session_state.get("ui_labor_rate", 40.0)),

    'printer_price': float(st.session_state.get("ui_printer_price", float(printer_defaults["price"]))),
    'residual_value_pct': float(st.session_state.get("ui_residual_val", 20)) / 100.0,
    'depreciation_years': int(st.session_state.get("ui_depreciation_years", 5)),
    'est_prints_per_year': int(st.session_state.get("ui_est_prints_per_year", 12)),

    'crane_rate': float(st.session_state.get("ui_crane_rate", 1500.0)),
    'num_homes': int(num_homes),

    'rebar_cost_ft': float(st.session_state["base_rebar_cost_ft"]),
    'misc_bos_sqft': float(st.session_state["base_misc_bos_sqft"]),

    'sga_per_home': float(st.session_state.get("ui_sga_per_home", 0.0)),
    'printer_upfront_pct': float(st.session_state.get("ui_printer_upfront_pct", 20.0)) / 100.0,
    'printer_acquisition_type': st.session_state.get("ui_printer_acquisition_type", "Cash (Own)"),
    'printer_monthly_payment': float(st.session_state.get("ui_printer_monthly_payment", 0.0)),
}

# ---------------------------------------------------------
# 11. DISPLAY TABS
# ---------------------------------------------------------
tab_single, tab_compare = st.tabs(["📊 Single Estimate", "⚖️ Multi-Scenario"])

# =========================================================
# TAB 1: SINGLE ESTIMATE
# =========================================================
with tab_single:
    res = calculate_costs(inputs_a, is_metric)

    for w in res['warnings']:
        st.warning(w)

    # Pre-compute Job Cash Reality totals ONCE so the headline metric can match the table TOTAL.
    project_months = int(res.get("project_months", 1))
    project_months = max(1, project_months)

    mat_project = float(res.get("mat_cost", 0.0)) * num_homes
    labor_project = float(res.get("labor_cost", 0.0)) * num_homes
    logistics_project = float(res.get("logistics_cost", 0.0)) * num_homes
    bos_project = float(res.get("bos_cost", 0.0)) * num_homes

    lease_project = float(res.get("printer_lease_expense_per_home", 0.0) or 0.0) * num_homes
    debt_service_project = float(res.get("printer_debt_service_per_home", 0.0) or 0.0) * num_homes

    total_job_cash = mat_project + labor_project + logistics_project + bos_project + lease_project + debt_service_project
    avg_monthly_burn = total_job_cash / project_months if project_months > 0 else 0.0

    st.markdown("### 💰 Wall Package Economics")

    m1, m2, m3 = st.columns(3)
    m1.metric("Cash Cost / Wall Package (excl. printer purchase)", fmt_money(res['cash_cost_total']), delta="Cash COGS")
    m2.metric("Days per Home", f"{res['days_per_home']:.1f} Days", delta="Includes Setup", delta_color="off")
    m3.metric("Total Cash Required", fmt_money(total_job_cash), delta="Breakdown Below")

    info_lines = [
        f"📌 **Cash Cost of {fmt_money(res['cash_cost_total'])}** = COGS for the wall scope (material, labor, logistics).",
        "**It excludes the printer purchase.**",
        f"Project timeline estimate: **{res['total_project_days']:.1f} days (~{res['project_months']} months)**."
    ]
    st.info(" ".join(info_lines))
    st.divider()

    # ---------------------------------------------------------
    # 🧰 JOB CASH REALITY PANEL
    # ---------------------------------------------------------
    st.markdown("### 🧰 Job Cash Reality")
    with st.container(border=True):
        st.metric("Monthly Cash Burn (avg.)", fmt_money(avg_monthly_burn), f"~{project_months} months")

        breakdown = [
            {"Component": "Material", "Project Total": mat_project},
            {"Component": "Labor", "Project Total": labor_project},
            {"Component": "Logistics", "Project Total": logistics_project},
            {"Component": "Integration", "Project Total": bos_project},
        ]
        if lease_project > 0:
            breakdown.append({"Component": "Printer lease/rent (operating expense)", "Project Total": lease_project})
        if debt_service_project > 0:
            breakdown.append({"Component": "Printer Debt Service", "Project Total": debt_service_project})

        df_breakdown = pd.DataFrame(breakdown)
        df_breakdown["Per Month (avg.)"] = df_breakdown["Project Total"] / project_months

        totals_row = {
            "Component": "TOTAL",
            "Project Total": float(df_breakdown["Project Total"].sum()),
            "Per Month (avg.)": float(df_breakdown["Per Month (avg.)"].sum()),
        }
        df_breakdown = pd.concat([df_breakdown, pd.DataFrame([totals_row])], ignore_index=True)

        df_breakdown_show = df_breakdown.copy()
        df_breakdown_show["Project Total"] = df_breakdown_show["Project Total"].map(fmt_money)
        df_breakdown_show["Per Month (avg.)"] = df_breakdown_show["Per Month (avg.)"].map(fmt_money)

        st.dataframe(df_breakdown_show, use_container_width=True, hide_index=True)

        acq = res.get("printer_acquisition_type", "")
        pay = float(res.get("printer_monthly_payment", 0.0) or 0.0)
        up = float(res.get("printer_upfront_cash", 0.0) or 0.0)
        if pay > 0 or up > 0:
            pay_str = fmt_money(pay).replace("$", r"\$")
            up_str  = fmt_money(up).replace("$", r"\$")

            st.markdown(
                f"**Printer structure:** {acq}  \n"
                f"**Monthly payment:** {pay_str}/mo  \n"
                f"**Upfront printer cash:** {up_str}"
            )

        st.caption(
            "Project total is the per-home wall cost multiplied by the number of homes. "
        )

    # ---------------------------------------------------------
    # BID ECONOMICS (Cash Bridge)
    # ---------------------------------------------------------
    g1, g2 = st.columns([1, 1])

    with g1:
        with st.container(border=True):
            st.markdown("##### 🏦 Bid Economics")

            default_sale = round_to_nearest_thousand(res['grand_total'] * 1.3)
            sale_price = st.number_input("Target Wall Package Sale Price ($)", value=int(default_sale), step=1000, key="ui_sale_price")

            # Core cash numbers (per home)
            cash_cogs_total = float(res.get("cash_cogs_total", 0.0))
            cash_before_printer = sale_price - cash_cogs_total - float(inputs_a.get("sga_per_home", 0.0))

            printer_acq = res.get("printer_acquisition_type", "")
            printer_payment_alloc = 0.0
            printer_note = ""

            # Finance (Own): show allocated debt service per home
            if printer_acq == "Finance (Own)" and float(res.get("printer_debt_service_per_home", 0.0)) > 0:
                printer_payment_alloc = float(res.get("printer_debt_service_per_home", 0.0))
                printer_note = "If printer is financed --> printer payment shown separately. If printer is leased/rented --> payment shown in wall package costs."
            # Lease/Rent: payment is already included in cash_cogs_total, so allocated = 0
            elif printer_acq == "Lease/Rent (Expense)":
                printer_payment_alloc = 0.0
                printer_note = "If printer is financed --> printer payment shown separately. If printer is leased/rented --> payment shown in wall package costs."

            cash_left_after_printer = cash_before_printer - printer_payment_alloc

            bridge_rows = [
                {"Line": "Bid Price (Per Home)", "Amount": float(sale_price)},
                {"Line": "Wall Package Cash Costs (Per Home)", "Amount": float(cash_cogs_total)},
                {"Line": "Cash Before Printer Payment (Per Home)", "Amount": float(cash_before_printer)},
                {"Line": "Printer Payment Allocated (Per Home)", "Amount": float(printer_payment_alloc)},
                {"Line": "Cash After Printer Payment (Per Home)", "Amount": float(cash_left_after_printer)},
            ]
            df_bridge = pd.DataFrame(bridge_rows)
            df_bridge_show = df_bridge.copy()
            df_bridge_show["Amount"] = df_bridge_show["Amount"].map(fmt_money)

            st.dataframe(df_bridge_show, use_container_width=True, hide_index=True)

            if printer_note:
                st.caption(printer_note)

            # Payback on upfront printer cash (unchanged logic)
            upfront_cash = float(res.get("printer_upfront_cash", 0.0) or 0.0)
            basis_profit = cash_left_after_printer  # aligns with the bridge bottom line

            if upfront_cash > 0 and basis_profit > 0:
                payback_homes = upfront_cash / basis_profit
                payback_label = f"{payback_homes:.1f} Homes"
            elif upfront_cash == 0:
                payback_label = "N/A"
            else:
                payback_label = "Never"

            st.metric("Payback on Upfront Printer Cash", payback_label, f"Upfront: {fmt_money(upfront_cash)}")

    with g2:
        with st.container(border=True):
            st.markdown("##### Cost Components")
            cost_data = pd.DataFrame([
                {"Category": "Material", "Cost": res['mat_cost']},
                {"Category": "Labor", "Cost": res['labor_cost']},
                {"Category": "Logistics", "Cost": res['logistics_cost']},
                {"Category": "Integration", "Cost": res['bos_cost']},
                {"Category": "Printer Depr/Amort", "Cost": res['machine_cost']},
            ])

            c = alt.Chart(cost_data).mark_arc(innerRadius=50).encode(
                theta=alt.Theta("Cost:Q"),
                color=alt.Color("Category:N"),
                tooltip=["Category", alt.Tooltip("Cost:Q", format="$,.0f")]
            )
            st.altair_chart(c, use_container_width=True)

    # ---------------------------------------------------------
    # ADVANCED: Accounting P&L (collapsed)
    # ---------------------------------------------------------
    with st.expander("📑 Accounting P&L", expanded=False):
        pnl_df, pnl_metrics = build_pnl_df(res, sale_price, float(inputs_a.get("sga_per_home", 0.0)))

        st.caption(
            "Accounting view includes printer depreciation/amortization. "
            "Project column simply multiplies per-home accounting values by the number of homes."
        )

        acct_per_home = pnl_df[["Line Item", "Accounting P&L"]].copy()
        acct_per_home.rename(columns={"Accounting P&L": "Per Home"}, inplace=True)
        acct_per_home["Entire Project"] = acct_per_home["Per Home"] * float(num_homes)

        show_df = acct_per_home.copy()
        show_df["Per Home"] = show_df["Per Home"].map(lambda x: f"${x:,.0f}")
        show_df["Entire Project"] = show_df["Entire Project"].map(lambda x: f"${x:,.0f}")
        st.dataframe(show_df, use_container_width=True, hide_index=True)

        ebitda_row = pnl_df.loc[pnl_df["Line Item"] == "EBITDA"].iloc[0]
        ebit_row = pnl_df.loc[pnl_df["Line Item"] == "EBIT (Operating Profit)"].iloc[0]

        m1, m2, m3 = st.columns(3)
        m1.metric("EBITDA (Per Home)", fmt_money(float(ebitda_row["Accounting P&L"])))
        m2.metric("EBIT (Per Home)", fmt_money(float(ebit_row["Accounting P&L"])))
        m3.metric("EBIT (Entire Project)", fmt_money(float(ebit_row["Accounting P&L"]) * float(num_homes)))

        metrics_show = pnl_metrics[["Metric", "Accounting"]].copy()
        metrics_show["Accounting"] = metrics_show["Accounting"].map(lambda x: f"{x*100:.1f}%")
        st.dataframe(metrics_show, use_container_width=True, hide_index=True)

        csv_pnl = acct_per_home.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download P&L CSV", csv_pnl, "3dcp_accounting_pnl.csv", "text/csv")

    # Stats Row
    st.markdown("#### ⚙️ Per-Home Print Stats")
    st.caption("These stats are modeled **per home** for the wall scope.")

    if is_metric:
        dist_display = f"{(res['total_path_length_ft'] * FT_TO_M) / 1000:.2f} km"
        weight_display = f"{res['weight_tons'] * (1 / TONNE_TO_TON):.1f} Tonnes"
    else:
        dist_display = f"{res['total_path_length_ft'] / 5280:.2f} Miles"
        weight_display = f"{res['weight_tons']:.1f} Tons"

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Print Time", f"{res['real_print_time_hr']:.1f} hrs")
    s2.metric("Material", weight_display)
    s3.metric("Nozzle Path", dist_display)
    s4.metric("Cost Efficiency", f"{res['cost_per_area']:.2f} {area_unit}")

# =========================================================
# TAB 2: MULTI-SCENARIO
# =========================================================
with tab_compare:
    st.markdown("### ⚖️ Side-by-Side")
    num_alts = st.radio("Add Scenarios:", [1, 2, 3], horizontal=True, key="ui_num_alts")
    st.divider()

    scenario_results = []
    scenario_results.append({"id": "A", "label": f"A: {selected_printer}", "inputs": inputs_a, "res": res})

    cols = st.columns(num_alts + 1)
    with cols[0]:
        st.info(f"**A: {selected_printer}** (Base)")

    printer_opts = ["Custom"] + list(PRINTERS.keys())
    mat_opts = ["Custom"] + list(MATERIALS.keys())

    for i in range(num_alts):
        letter = ["B", "C", "D"][i]
        with cols[i + 1]:
            st.warning(f"**{letter} (Alt)**")
            sel_p = st.selectbox(f"Printer {letter}", printer_opts, index=1, key=f"p{i}")
            sel_m = st.selectbox(f"Material {letter}", mat_opts, index=1, key=f"m{i}")

            new_in = inputs_a.copy()

            if sel_p == "Custom":
                new_in['printer_price'] = st.number_input("Price", value=250000, step=5000, key=f"cp{i}")
                new_in['print_speed_mm_s'] = st.number_input("Speed", value=200, step=10, key=f"cs{i}")
                new_in['efficiency'] = st.slider("Eff", 0.3, 0.9, 0.6, key=f"cef{i}")
                new_in['crew_size'] = st.number_input("Crew", value=2, step=1, key=f"cc{i}")
            else:
                p_def = get_printer_specs(sel_p)
                new_in['printer_price'] = p_def['price']
                new_in['print_speed_mm_s'] = p_def['speed_mm_s']
                new_in['efficiency'] = p_def['efficiency']
                new_in['crew_size'] = p_def['crew_size']
                new_in['setup_days'] = p_def['setup_days']
                new_in['teardown_days'] = p_def['teardown_days']
                new_in['layer_h_mm'] = p_def['layer_height_mm']
                new_in['bead_w_mm'] = p_def['bead_width_mm']

            if sel_m == "Custom":
                new_in['mat_price_ton'] = st.number_input("$/Ton", value=100, step=10, key=f"cm{i}")
                new_in['final_density_lbs_ft3'] = 145
                new_in['waste_pct'] = 0.05
            else:
                m_def = get_material_specs(sel_m)
                new_in['mat_price_ton'] = m_def['price_ton']
                new_in['final_density_lbs_ft3'] = m_def['density_lbs_ft3']
                new_in['waste_pct'] = m_def['waste_pct']

            r_alt = calculate_costs(new_in, is_metric)
            scenario_results.append({"id": letter, "label": f"{letter}: {sel_p}", "inputs": new_in, "res": r_alt})

    st.markdown("#### 📉 Cost Breakdown (Accrual)")
    chart_data = []
    for s in scenario_results:
        for cat, cost in [
            ("Material", s['res']['mat_cost']),
            ("Labor", s['res']['labor_cost']),
            ("Logistics", s['res']['logistics_cost']),
            ("Integration", s['res']['bos_cost']),
            ("Printer Depr/Amort", s['res']['machine_cost'])
        ]:
            chart_data.append({"Scenario": s['label'], "Category": cat, "Cost": cost})

    st.altair_chart(
        alt.Chart(pd.DataFrame(chart_data)).mark_bar().encode(
            x=alt.X('Scenario:N', sort=None, axis=alt.Axis(labelAngle=-25)),
            y=alt.Y('Cost:Q'),
            color=alt.Color('Category:N'),
            tooltip=['Scenario', 'Category', alt.Tooltip('Cost:Q', format='$,.0f')]
        ),
        use_container_width=True
    )

    st.markdown("#### 📋 Detailed Comparison Matrix")

    def fmt_num(x): return f"{x:.2f}"
    def fmt_pct(x): return f"{x * 100:.0f}%"

    row_defs = [
        ("Hardware Price", "$", lambda s: fmt_money(s['inputs']['printer_price'])),
        ("Upfront Printer Cash", "$", lambda s: fmt_money(s['res'].get('printer_upfront_cash', 0.0))),
        ("Print Speed", "mm/s", lambda s: f"{s['inputs']['print_speed_mm_s']}"),
        ("Machine Efficiency", "%", lambda s: fmt_pct(s['inputs']['efficiency'])),
        ("Total Print Time", "Hours", lambda s: fmt_num(s['res']['real_print_time_hr'])),
        ("Cash Cost (Wall Scope)", "$", lambda s: fmt_money(s['res']['cash_cost_total'])),
        ("Accrual Cost (Wall Scope)", "$", lambda s: fmt_money(s['res']['grand_total'])),
        ("Upfront Capital Required", "$", lambda s: fmt_money(s['res']['cash_required'])),
        ("Days/Home", "Days", lambda s: fmt_num(s['res']['days_per_home'])),
        ("Cost per Area", area_unit, lambda s: fmt_num(s['res']['cost_per_area'])),
    ]

    matrix_data = []
    for metric_name, unit, val_func in row_defs:
        row = {"Metric": metric_name, "Unit": unit}
        for scen in scenario_results:
            row[scen['label']] = val_func(scen)
        matrix_data.append(row)

    df_matrix = pd.DataFrame(matrix_data)
    st.dataframe(df_matrix, use_container_width=True, hide_index=True)

    csv = df_matrix.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, "3dcp_comparison.csv", "text/csv")

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
