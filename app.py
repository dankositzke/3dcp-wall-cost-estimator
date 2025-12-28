import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import math

# ---------------------------------------------------------
# 0. PAGE CONFIG (must be first Streamlit command)
# ---------------------------------------------------------
st.set_page_config(page_title="3D Concrete Printing: Wall Cost Estimator", page_icon="🏗️", layout="wide")

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
        "crew_size": 3, "efficiency": 0.65, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "CyBe RC (Robot Crawler)": {
        "price": 230000, "speed_mm_s": 250, "setup_days": 0.5, "teardown_days": 0.5,
        "crew_size": 2, "efficiency": 0.60, "bead_width_mm": 40, "layer_height_mm": 15
    },
    "MudBots (25x25 Model)": {
        "price": 145000, "speed_mm_s": 100, "setup_days": 2.0, "teardown_days": 2.0,
        "crew_size": 3, "efficiency": 0.55, "bead_width_mm": 40, "layer_height_mm": 20
    },
    "RIC Technology RIC-M1": {
        "price": 250000, "speed_mm_s": 150, "setup_days": 0.2, "teardown_days": 0.2,
        "crew_size": 2, "efficiency": 0.70, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "X-Hab 3D MX3DP": {
        "price": 450000, "speed_mm_s": 250, "setup_days": 0.1, "teardown_days": 0.1,
        "crew_size": 3, "efficiency": 0.65, "bead_width_mm": 45, "layer_height_mm": 20
    },
    "Coral 3DCP (Mobile Unit)": {
        "price": 350000, "speed_mm_s": 330, "setup_days": 0.2, "teardown_days": 0.2,
        "crew_size": 2, "efficiency": 0.80, "bead_width_mm": 60, "layer_height_mm": 20
    },
    "Alquist 3D A1X": {
        "price": 450000, "speed_mm_s": 200, "setup_days": 1.0, "teardown_days": 1.0,
        "crew_size": 3, "efficiency": 0.70, "bead_width_mm": 50, "layer_height_mm": 20
    },
    "SQ4D ARCS": {
        "price": 400000, "speed_mm_s": 250, "setup_days": 2.5, "teardown_days": 2.0,
        "crew_size": 3, "efficiency": 0.75, "bead_width_mm": 80, "layer_height_mm": 25
    }
}

MATERIALS = {
    "Local Concrete + D.fab": {"type": "Admix", "price_ton": 80, "density_lbs_ft3": 145, "waste_pct": 0.10},
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
        {"Line Item": "COGS — BOS", "Cash P&L": res.get("bos_cost", 0.0), "Accounting P&L": res.get("bos_cost", 0.0)},
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
# 4. THE PHYSICS ENGINE & AUDITOR
# ---------------------------------------------------------
def calculate_costs(p, is_metric: bool):
    audit = {}
    warnings = []

    safe_eff = max(0.01, p['efficiency'])

    if safe_eff > 0.90:
        warnings.append("⚠️ OEE > 90% is extremely aggressive for construction.")
    if p['print_speed_mm_s'] > 300 and p['layer_h_mm'] > 25:
        warnings.append("⚠️ High Speed + High Layer Height may cause slump/collapse.")

    # A. Geometry
    linear_wall_ft = p['sq_ft_home'] * p['wall_density']
    wall_sq_ft = linear_wall_ft * p['wall_height_ft']
    wall_height_mm = p['wall_height_ft'] * 304.8

    layer_h_mm_safe = max(0.5, float(p['layer_h_mm']))
    bead_w_mm_safe = max(1.0, float(p['bead_w_mm']))

    total_layers = wall_height_mm / layer_h_mm_safe
    total_path_length_ft = linear_wall_ft * total_layers * p['passes_per_layer']

    audit['Geometry'] = (
        f"Wall Length: {linear_wall_ft:.0f} ft | Wall Area: {wall_sq_ft:,.0f} ft² | "
        f"Layers: {int(total_layers)} | Path: {total_path_length_ft:,.0f} ft"
    )

    # B. Time (complexity penalty + OEE)
    raw_avg_speed = p['print_speed_mm_s'] * (1 - p['complexity_factor'])
    avg_speed_mm_s = max(1.0, raw_avg_speed)

    speed_ft_hr = avg_speed_mm_s * 11.811
    theoretical_time_hr = total_path_length_ft / speed_ft_hr
    real_print_time_hr = theoretical_time_hr / safe_eff

    print_days = real_print_time_hr / SHIFT_HOURS
    total_project_days = (p['setup_days'] + p['teardown_days']) * p['moves_count'] + (print_days * p['num_homes'])
    days_per_home = total_project_days / p['num_homes']

    project_months = max(1, int(math.ceil(total_project_days / 30.0)))

    audit['Time'] = (
        f"Avg Speed: {avg_speed_mm_s:.0f} mm/s | Print Days: {print_days:.1f} | "
        f"Moves: {p['moves_count']} | Project: {total_project_days:.1f} days (~{project_months} mo)"
    )

    # C. Material
    vol_cu_ft = total_path_length_ft * (layer_h_mm_safe * MM_TO_FT) * (bead_w_mm_safe * MM_TO_FT)
    weight_lbs = vol_cu_ft * p['final_density_lbs_ft3']
    weight_tons = weight_lbs / 2000.0
    total_mat_cost_per_home = weight_tons * p['mat_price_ton'] * (1 + p['waste_pct'])

    flow_rate_l_min = (avg_speed_mm_s * bead_w_mm_safe * layer_h_mm_safe * 60) / 1_000_000.0
    if flow_rate_l_min > 30:
        warnings.append(f"⚠️ Flow Rate {flow_rate_l_min:.1f} L/min exceeds typical pump capacity (20-30 L/min).")

    # D. Labor
    setup_hrs_per_move = p['setup_days'] * SHIFT_HOURS
    teardown_hrs_per_move = p['teardown_days'] * SHIFT_HOURS

    labor_setup_per_move = (setup_hrs_per_move + teardown_hrs_per_move) * p['crew_size'] * p['labor_rate']
    labor_print_per_home = real_print_time_hr * p['crew_size'] * p['labor_rate']

    total_setup_labor_project = labor_setup_per_move * p['moves_count']
    total_print_labor_project = labor_print_per_home * p['num_homes']
    total_labor_cost_per_home = (total_setup_labor_project + total_print_labor_project) / p['num_homes']

    # E. Logistics (cash)
    logistics_cost_per_move = (p['setup_days'] + p['teardown_days']) * p['crane_rate']
    total_logistics_cost = logistics_cost_per_move * p['moves_count']
    logistics_cost_per_home = total_logistics_cost / p['num_homes']

    # F. BOS (cash)
    rebar_total = linear_wall_ft * p['rebar_cost_ft']
    misc_bos_total = wall_sq_ft * p['misc_bos_sqft']
    total_bos_cost = rebar_total + misc_bos_total

    # ---------------------------------------------------------
    # PRINTER ACQUISITION LOGIC
    # ---------------------------------------------------------
    printer_upfront_pct = float(p.get("printer_upfront_pct", 0.0))
    printer_upfront_cash = p['printer_price'] * printer_upfront_pct

    printer_monthly_payment = float(p.get("printer_monthly_payment", 0.0))
    printer_acq_type = p.get("printer_acquisition_type", "Cash (Own)")  # "Finance (Own)" or "Lease/Rent (Expense)" or "Cash (Own)"

    own_printer = (printer_acq_type != "Lease/Rent (Expense)")

    # Non-cash D&A only if owned
    if own_printer:
        machine_cost_per_year = (p['printer_price'] * (1 - p['residual_value_pct'])) / p['depreciation_years']
        machine_cost_per_home = machine_cost_per_year / p['est_prints_per_year']
    else:
        machine_cost_per_home = 0.0

    # Lease/Rent: payment is operating expense (cash COGS)
    printer_lease_expense_project = 0.0
    printer_lease_expense_per_home = 0.0
    if (not own_printer) and printer_monthly_payment > 0:
        printer_lease_expense_project = printer_monthly_payment * project_months
        printer_lease_expense_per_home = printer_lease_expense_project / p['num_homes']

    # Finance (Own): payment is cash flow, not P&L expense
    printer_debt_service_project = 0.0
    printer_debt_service_per_home = 0.0
    if own_printer and printer_acq_type == "Finance (Own)" and printer_monthly_payment > 0 and printer_upfront_pct < 1.0:
        printer_debt_service_project = printer_monthly_payment * project_months
        printer_debt_service_per_home = printer_debt_service_project / p['num_homes']

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
        area_m2 = p['sq_ft_home'] / SQ_M_TO_SQ_FT
        cost_per_area = grand_total / area_m2
        home_area = area_m2
    else:
        cost_per_area = grand_total / p['sq_ft_home']
        home_area = p['sq_ft_home']

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
st.title("🏗️ 3D Concrete Printing: Wall Cost Estimator")
st.markdown("### Assess Cost Comparisons To Traditional Methods")
st.divider()

# ---------------------------------------------------------
# 7. MAIN CONTROL PANEL (Project + Compare Mode)
# ---------------------------------------------------------
with st.container(border=True):
    st.markdown("#### Project Configuration")

    unit_col, _ = st.columns([1, 2])
    with unit_col:
        unit_system = st.radio("Unit System:", ["Imperial (US)", "Metric (EU)"], horizontal=True)

    is_metric = unit_system == "Metric (EU)"
    area_unit = "$/m²" if is_metric else "$/sqft"
    wall_area_unit = "$/m² wall" if is_metric else "$/sqft wall"
    wall_len_unit = "$/m wall" if is_metric else "$/lf wall"

    compare_label_finished = f"Δ vs my current finished home cost ({'$ / m²' if is_metric else '$ / ft²'})"
    compare_options = [
        "No baseline, just 3DCP wall cost",
        compare_label_finished,
        "Δ vs my current wall package cost",
    ]
    compare_mode = st.selectbox(
        "How do you want to compare?",
        compare_options,
        index=0,
        help="Pick the baseline you actually know. Most builders know finished-home $/area; some know wall-package pricing."
    )

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
        num_homes = st.number_input("Number of Homes In Project", min_value=1, value=10, step=1)
    with c4:
        IMPERIAL_DEFAULT_SQFT = 1500
        if is_metric:
            default_sqm = int(IMPERIAL_DEFAULT_SQFT / SQ_M_TO_SQ_FT)
            sq_m_input = st.number_input("Avg. Sq Meters", value=default_sqm, step=1, format="%d")
            sq_ft_home = sq_m_input * SQ_M_TO_SQ_FT
        else:
            sq_ft_home = st.number_input("Avg. Sq Ft", value=IMPERIAL_DEFAULT_SQFT, step=10, format="%d")

# ---------------------------------------------------------
# 8. BASELINE INPUTS (shown depending on compare_mode)
# ---------------------------------------------------------
baseline_finished_cost_per_area = None
baseline_wall_share_pct = None
baseline_wall_rate_type = None
baseline_wall_rate_value = None
baseline_days_enabled = False
baseline_days_value = None

if compare_mode != "No baseline, just 3DCP wall cost":
    with st.container(border=True):
        st.markdown("#### Baseline Inputs (for Apples-to-Apples)")

        if compare_mode == compare_label_finished:
            default_finished = 2200 if is_metric else 200
            step_finished = 50 if is_metric else 10
            baseline_finished_cost_per_area = st.number_input(
                f"My current finished-home cost ({'$ / m²' if is_metric else '$ / ft²'})",
                value=float(default_finished),
                step=float(step_finished),
                help="Your all-in finished build cost in your market. Used only as a baseline to compute a wall-system delta."
            )

            baseline_wall_share_pct = st.slider(
                "Estimated share of finished-home cost that your wall system represents (%)",
                min_value=5,
                max_value=35,
                value=12,
                step=1,
                help="If you don’t know wall-package cost directly, estimate the % of total finished cost attributable to the wall scope you're comparing."
            ) / 100.0

            baseline_days_enabled = st.checkbox("I want to include schedule delta (optional)", value=False)
            if baseline_days_enabled:
                baseline_days_value = st.number_input(
                    "My current wall package duration (days per home)",
                    value=10.0,
                    step=1.0,
                    help="Optional. If you know it, we’ll show Δ days vs 3DCP for the same wall scope."
                )

        elif compare_mode == "Δ vs my current wall package cost":
            wall_rate_types = [f"{wall_area_unit}", f"{wall_len_unit}", "$/home (wall package)"]

            baseline_wall_rate_type = st.radio(
                "How do you price your current wall package?",
                wall_rate_types,
                horizontal=True
            )

            if baseline_wall_rate_type == wall_area_unit:
                default_wall_area_rate = 55.0 if is_metric else 5.0
                baseline_wall_rate_value = st.number_input(
                    f"My current wall package rate ({wall_area_unit})",
                    value=float(default_wall_area_rate),
                    step=1.0,
                    help="Your wall package cost priced per wall surface area."
                )
            elif baseline_wall_rate_type == wall_len_unit:
                default_wall_len_rate = 180.0 if is_metric else 55.0
                baseline_wall_rate_value = st.number_input(
                    f"My current wall package rate ({wall_len_unit})",
                    value=float(default_wall_len_rate),
                    step=1.0,
                    help="Your wall package cost priced per linear wall length."
                )
            else:
                default_wall_home = 45000.0
                baseline_wall_rate_value = st.number_input(
                    "My current wall package cost ($/home)",
                    value=float(default_wall_home),
                    step=1000.0,
                    help="Your wall package cost priced per home (same completion level you're comparing)."
                )

            baseline_days_enabled = st.checkbox("I want to include schedule delta (optional)", value=False)
            if baseline_days_enabled:
                baseline_days_value = st.number_input(
                    "My current wall package duration (days per home)",
                    value=10.0,
                    step=1.0,
                    help="Optional. If you know it, we’ll show Δ days vs 3DCP for the same wall scope."
                )

# ---------------------------------------------------------
# 9. ADVANCED OVERRIDES
# ---------------------------------------------------------
printer_defaults = PRINTERS[selected_printer]
mat_defaults = MATERIALS[selected_material]

st.write("")

with st.expander("🛠️ Advanced Assumptions (Click to Edit)"):
    tab_fin, tab_geo, tab_ops, tab_bos = st.tabs(
        ["💵 Financials", "📐 Geometry & Complexity", "⚙️ Operations", "🧱 BOS & Integration"]
    )

    with tab_fin:
        f1, f2, f3 = st.columns(3)
        with f1:
            st.markdown("**Material Costs**")
            if is_metric:
                def_price = int(mat_defaults["price_ton"] / (1 / TONNE_TO_TON))
                u_price = st.number_input("Material Price ($/Tonne)", value=def_price, step=10)
                mat_price_ton = u_price * (1 / TONNE_TO_TON)
            else:
                mat_price_ton = st.number_input("Material Price ($/Ton)", value=int(mat_defaults["price_ton"]), step=10)

            waste_pct_in = st.number_input(
                "Material Waste %",
                value=float(mat_defaults["waste_pct"] * 100),
                step=1.0,
                format="%.1f"
            )
            waste_pct = waste_pct_in / 100.0

        with f2:
            st.markdown("**Labor, Logistics & Overhead**")
            labor_rate = st.number_input("Crew Labor Rate ($/hr)", value=40, step=5)
            crane_rate = st.number_input("Crane Rate ($/day)", value=1500, step=100)
            sga_per_home = st.number_input(
                "SG&A / Overhead ($/home)",
                value=0,
                step=500,
                help="Optional overhead per home (supervision, admin, insurance, office, sales support, etc.)."
            )

        with f3:
            st.markdown("**Printer (Asset + Cash Structure)**")

            left, right = st.columns([1, 1], gap="large")

            with left:
                printer_price = st.number_input(
                    "Printer Hardware Cost ($)",
                    value=int(printer_defaults["price"]),
                    step=5000
                )
                depreciation_years = st.number_input(
                    "Amortization Period (Yrs)",
                    value=5,
                    min_value=1
                )
                residual_val = st.number_input(
                    "Residual Value (%)",
                    value=20,
                    step=5
                )
                residual_value_pct = residual_val / 100.0

                est_prints_per_year = st.number_input(
                    "Annual Utilization (Homes/Yr)",
                    value=12,
                    min_value=1
                )

            with right:
                DEFAULT_UPFRONT_PCT = 20
                DEFAULT_APR = 0.10
                term_months = max(1, int(depreciation_years * 12))

                printer_upfront_pct_in = st.number_input(
                    "Upfront Printer Cash (%)",
                    value=DEFAULT_UPFRONT_PCT,
                    min_value=0,
                    max_value=100,
                    step=5,
                    help="Default 20%. If < 100%, monthly payment auto-fills using 10% APR and term = amortization years."
                )
                printer_upfront_pct = printer_upfront_pct_in / 100.0

                remaining_principal = printer_price * (1 - printer_upfront_pct)
                suggested_payment = calc_monthly_payment(
                    principal=remaining_principal,
                    annual_rate=DEFAULT_APR,
                    months=term_months
                )

                printer_acquisition_type = "Cash (Own)"
                printer_monthly_payment = 0.0

                if printer_upfront_pct_in < 100:
                    printer_acquisition_type = st.radio(
                        "Printer acquisition type",
                        ["Finance (Own)", "Lease/Rent (Expense)"],
                        horizontal=True,
                        help=(
                            "Finance (Own): D&A applies; payments shown as cash flow. "
                            "Lease/Rent: payment treated as operating expense (COGS); no D&A."
                        )
                    )

                    auto_calc = st.checkbox(
                        "Auto-calc monthly payment (10% APR)",
                        value=True,
                        help=f"Uses remaining balance and term = {term_months} months."
                    )

                    if auto_calc:
                        printer_monthly_payment = float(round(suggested_payment, 0))
                        st.number_input(
                            "Monthly Printer Payment ($/month)",
                            value=float(printer_monthly_payment),
                            step=500.0,
                            min_value=0.0,
                            disabled=True
                        )
                    else:
                        printer_monthly_payment = st.number_input(
                            "Monthly Printer Payment ($/month)",
                            value=float(round(suggested_payment, 0)),
                            step=500.0,
                            min_value=0.0
                        )

                    st.caption(f"Default calc: 10% APR, {term_months} months, remaining balance = {fmt_money(remaining_principal)}")
                else:
                    printer_upfront_pct = printer_upfront_pct_in / 100.0
                    printer_acquisition_type = "Cash (Own)"
                    printer_monthly_payment = 0.0

    with tab_geo:
        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown("**Wall Dimensions**")
            wall_density = st.number_input(
                "Wall Density Factor",
                value=0.20,
                format="%.2f",
                help="Linear wall ft per sq ft of floor. Higher = more wall length (more rooms/corners) per area."
            )
            if is_metric:
                wall_height_m = st.number_input("Wall Height (m)", value=2.75, step=0.1)
                wall_height_ft = wall_height_m * M_TO_FT
            else:
                wall_height_ft = st.number_input("Wall Height (ft)", value=9.0, step=0.5)

        with g2:
            st.markdown("**Print Resolution**")
            if is_metric:
                layer_h_mm = st.number_input("Layer Height (mm)", value=float(printer_defaults["layer_height_mm"]), step=1.0, min_value=1.0)
                bead_w_mm = st.number_input("Bead Width (mm)", value=float(printer_defaults["bead_width_mm"]), step=1.0, min_value=1.0)
            else:
                def_layer_in = printer_defaults["layer_height_mm"] * MM_TO_INCH
                def_bead_in = printer_defaults["bead_width_mm"] * MM_TO_INCH
                u_layer_in = st.number_input("Layer Height (in)", value=float(f"{def_layer_in:.3f}"), format="%.3f", min_value=0.001)
                u_bead_in = st.number_input("Bead Width (in)", value=float(f"{def_bead_in:.3f}"), format="%.3f", min_value=0.001)
                layer_h_mm = u_layer_in / MM_TO_INCH
                bead_w_mm = u_bead_in / MM_TO_INCH

            passes_per_layer = st.number_input("Passes per Layer", value=2, min_value=1, max_value=4, step=1)

        with g3:
            st.markdown("**Design Complexity**")
            complexity_factor = st.slider(
                "Geometry Complexity (Turns/Stops)",
                0.0, 0.9, 0.2,
                step=0.1,
                help=(
                    "Speed penalty for corners, jogs, openings, starts/stops, and path-planning overhead. "
                    "Applied BEFORE OEE. Example: 0.2 reduces effective speed by 20%."
                )
            )
            st.caption(f"Speed Penalty: -{int(complexity_factor * 100)}%")

    with tab_ops:
        o1, o2, o3 = st.columns(3)
        with o1:
            st.markdown("**Speed & Efficiency**")
            print_speed_mm_s = st.number_input("Max Print Speed (mm/s)", value=int(printer_defaults["speed_mm_s"]), step=10, min_value=10)
            efficiency_pct = st.number_input(
                "Machine Efficiency (OEE %)",
                value=int(printer_defaults["efficiency"] * 100),
                step=5,
                min_value=1,
                max_value=100,
                help=(
                    "Overall Equipment Effectiveness: % of the shift where the nozzle is actually extruding. "
                    "Captures downtime (refills, cleaning, troubleshooting, pauses, minor maintenance)."
                )
            )
            efficiency = efficiency_pct / 100.0

        with o2:
            st.markdown("**Site Crew**")
            crew_size = st.number_input("Crew Size (People)", value=int(printer_defaults["crew_size"]), step=1, min_value=1)

            moves_default = max(1, math.ceil(num_homes / 2))
            moves_count = st.number_input(
                "Printer Moves (Crane Lifts)",
                value=moves_default,
                step=1,
                min_value=1,
                help=(
                    "How many times the printer must be disassembled and moved via crane/rigging. "
                    "Rule of thumb: ~1 move per 2 homes (site layout can change this)."
                )
            )

        with o3:
            st.markdown("**Material Params**")
            if is_metric:
                def_dens = int(mat_defaults["density_lbs_ft3"] / KG_M3_TO_LBS_FT3)
                u_dens = st.number_input("Dry Density (kg/m³)", value=def_dens, step=10)
                final_density_lbs_ft3 = u_dens * KG_M3_TO_LBS_FT3
            else:
                final_density_lbs_ft3 = st.number_input("Dry Density (lbs/ft³)", value=int(mat_defaults["density_lbs_ft3"]), step=1)

    with tab_bos:
        st.markdown("**Mobilization**")
        b1, b2 = st.columns(2)
        with b1:
            setup_days = st.number_input("Setup Days (per move)", value=float(printer_defaults["setup_days"]), step=0.5, min_value=0.0)
        with b2:
            teardown_days = st.number_input("Teardown Days (per move)", value=float(printer_defaults["teardown_days"]), step=0.5, min_value=0.0)

        st.divider()
        st.caption("BOS = Balance of System: integration items not 3D printed (reinforcement, embeds, lintels, bucks, insulation fill, patching, etc.).")

        b3, b4 = st.columns(2)
        with b3:
            st.markdown("**Reinforcement (Rebar)**")
            if is_metric:
                rebar_cost_m = st.number_input(
                    "Rebar Cost ($/linear meter)",
                    value=6.5,
                    step=0.5,
                    help="BOS item: reinforcement required to make the printed wall structural."
                )
                rebar_cost_ft = rebar_cost_m * (1 / M_TO_FT)
            else:
                rebar_cost_ft = st.number_input(
                    "Rebar Cost ($/linear foot)",
                    value=2.0,
                    step=0.25,
                    help="BOS item: reinforcement required to make the printed wall structural."
                )

        with b4:
            st.markdown("**Insulation & Lintels**")
            if is_metric:
                misc_bos_sqm = st.number_input(
                    "Misc BOS ($/sq meter of wall)",
                    value=15.0,
                    step=1.0,
                    help="BOS bucket: non-printed integration items (lintels, bucks, embeds, insulation fill, patching, etc.)."
                )
                misc_bos_sqft = misc_bos_sqm * (1 / SQ_M_TO_SQ_FT)
            else:
                misc_bos_sqft = st.number_input(
                    "Misc BOS ($/sq ft of wall)",
                    value=1.5,
                    step=0.25,
                    help="BOS bucket: non-printed integration items (lintels, bucks, embeds, insulation fill, patching, etc.)."
                )

# ---------------------------------------------------------
# 10. SCENARIO INPUTS
# ---------------------------------------------------------
inputs_a = {
    'sq_ft_home': sq_ft_home, 'wall_density': wall_density, 'wall_height_ft': wall_height_ft,
    'layer_h_mm': layer_h_mm, 'passes_per_layer': passes_per_layer, 'print_speed_mm_s': print_speed_mm_s,
    'efficiency': efficiency, 'bead_w_mm': bead_w_mm, 'final_density_lbs_ft3': final_density_lbs_ft3,
    'mat_price_ton': mat_price_ton, 'waste_pct': waste_pct, 'setup_days': setup_days,
    'teardown_days': teardown_days, 'moves_count': moves_count, 'crew_size': crew_size,
    'labor_rate': labor_rate, 'printer_price': printer_price, 'residual_value_pct': residual_value_pct,
    'depreciation_years': depreciation_years, 'est_prints_per_year': est_prints_per_year,
    'crane_rate': crane_rate, 'num_homes': num_homes, 'rebar_cost_ft': rebar_cost_ft,
    'misc_bos_sqft': misc_bos_sqft, 'complexity_factor': complexity_factor,
    'sga_per_home': sga_per_home,

    'printer_upfront_pct': printer_upfront_pct,
    'printer_acquisition_type': printer_acquisition_type,
    'printer_monthly_payment': printer_monthly_payment,
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

    st.markdown("### 💰 Project Economics")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cash Cost / Wall Scope (excl. printer purchase)", fmt_money(res['cash_cost_total']), delta="Cash COGS")
    m2.metric("Accrual Cost / Wall Scope", fmt_money(res['grand_total']), delta="Accounting view")
    m3.metric("Days per Home", f"{res['days_per_home']:.1f} Days", delta="Includes Setup", delta_color="off")
    m4.metric("Upfront Capital Required", fmt_money(res['cash_required']), delta="Printer + 1st Project", delta_color="inverse")

    info_lines = [
        f"📌 **Cash Cost of {fmt_money(res['cash_cost_total'])}** = Cash COGS for the wall scope (material, labor, logistics, BOS).",
        "**It excludes the printer purchase.**",
        f"Project timeline estimate: **{res['total_project_days']:.1f} days (~{res['project_months']} months)**."
    ]
    st.info(" ".join(info_lines))
    st.divider()

    # Track baseline delta for Builder Decision Panel (cash)
    baseline_delta_cash_value = None
    baseline_delta_cash_pct = None
    baseline_delta_label = "Δ vs baseline (Cash)"

    # --- BASELINE COMPARISON (builder-friendly) ---
    if compare_mode != "No baseline, just 3DCP wall cost":
        with st.container(border=True):
            st.markdown("### 🍏🍏 Apples-to-Apples Comparison")

            wall_sq_ft = res["wall_sq_ft"]
            linear_wall_ft = res["linear_wall_ft"]
            home_area = res["home_area"]

            if is_metric:
                wall_area = wall_sq_ft / SQ_M_TO_SQ_FT
                wall_len = linear_wall_ft * FT_TO_M
                finished_unit = "$/m²"
                home_area_label = "m²"
                wall_area_label = "m²"
                wall_len_label = "m"
            else:
                wall_area = wall_sq_ft
                wall_len = linear_wall_ft
                finished_unit = "$/ft²"
                home_area_label = "ft²"
                wall_area_label = "ft²"
                wall_len_label = "ft"

            if compare_mode == compare_label_finished:
                baseline_total_home_cost = baseline_finished_cost_per_area * home_area
                baseline_wall_est = baseline_total_home_cost * baseline_wall_share_pct

                new_total_cash = baseline_total_home_cost - baseline_wall_est + res["cash_cost_total"]
                new_total_accrual = baseline_total_home_cost - baseline_wall_est + res["grand_total"]

                delta_cash = new_total_cash - baseline_total_home_cost
                delta_accrual = new_total_accrual - baseline_total_home_cost

                # store for decision panel
                baseline_delta_cash_value = delta_cash
                baseline_delta_cash_pct = safe_div(delta_cash, baseline_total_home_cost)
                baseline_delta_label = "Δ Finished Home Cost (Cash)"

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Baseline Finished Cost / Home", fmt_money(baseline_total_home_cost))
                c2.metric("Baseline Wall Budget (est.)", fmt_money(baseline_wall_est), f"{baseline_wall_share_pct*100:.0f}% of home")
                c3.metric("3DCP Wall Cost (Cash, excl. printer purchase)", fmt_money(res["cash_cost_total"]))
                c4.metric("Δ Home Cost (Cash)", fmt_signed_money(delta_cash), f"{baseline_delta_cash_pct*100:.1f}%")

                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Baseline Finished", f"{baseline_finished_cost_per_area:,.0f} {finished_unit}")
                d2.metric("New Finished (Cash)", f"{(new_total_cash / home_area):,.0f} {finished_unit}")
                d3.metric("New Finished (Accrual)", f"{(new_total_accrual / home_area):,.0f} {finished_unit}")
                d4.metric("Δ Home Cost (Accrual)", fmt_signed_money(delta_accrual), f"{safe_div(delta_accrual, baseline_total_home_cost)*100:.1f}%")

                if baseline_days_enabled and baseline_days_value is not None:
                    st.caption(f"⏱️ Schedule Δ (3DCP - baseline): **{res['days_per_home'] - baseline_days_value:+.1f} days/home**")

                st.caption(
                    "Note: This replaces an estimated wall share of your finished-home cost with the modeled 3DCP wall cost. "
                    "For tighter accuracy, use the wall-package baseline mode."
                )

            elif compare_mode == "Δ vs my current wall package cost":
                if baseline_wall_rate_type == wall_area_unit:
                    baseline_wall_cost = baseline_wall_rate_value * wall_area
                    baseline_basis = f"{baseline_wall_rate_value:,.2f} {wall_area_unit} × {wall_area:,.0f} {wall_area_label} wall"
                elif baseline_wall_rate_type == wall_len_unit:
                    baseline_wall_cost = baseline_wall_rate_value * wall_len
                    baseline_basis = f"{baseline_wall_rate_value:,.2f} {wall_len_unit} × {wall_len:,.0f} {wall_len_label} wall"
                else:
                    baseline_wall_cost = baseline_wall_rate_value
                    baseline_basis = "Direct $/home wall package"

                delta_cash = res["cash_cost_total"] - baseline_wall_cost
                delta_accrual = res["grand_total"] - baseline_wall_cost

                # store for decision panel
                baseline_delta_cash_value = delta_cash
                baseline_delta_cash_pct = safe_div(delta_cash, baseline_wall_cost)
                baseline_delta_label = "Δ Wall Package Cost (Cash)"

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Baseline Wall Package / Home", fmt_money(baseline_wall_cost))
                c2.metric("3DCP Wall Cost (Cash, excl. printer purchase)", fmt_money(res["cash_cost_total"]))
                c3.metric("Δ Wall Cost (Cash)", fmt_signed_money(delta_cash), f"{baseline_delta_cash_pct*100:.1f}%")
                c4.metric("Δ Wall Cost (Accrual)", fmt_signed_money(delta_accrual), f"{safe_div(delta_accrual, baseline_wall_cost)*100:.1f}%")

                st.caption(f"Baseline basis: {baseline_basis}")

                if baseline_days_enabled and baseline_days_value is not None:
                    st.caption(f"⏱️ Schedule Δ (3DCP - baseline): **{res['days_per_home'] - baseline_days_value:+.1f} days/home**")

                st.caption(
                    "Make sure your baseline wall package scope matches (structure, reinforcement, finishes readiness, etc.). "
                    "If scope differs, the delta will lie to you."
                )

    # ---------------------------------------------------------
    # 🧰 BUILDER DECISION PANEL (Cash View)
    # ---------------------------------------------------------
    st.markdown("### 🧰 Builder Decision Panel (Cash View)")
    with st.container(border=True):
        project_months = int(res.get("project_months", 1))
        project_months = max(1, project_months)

        # Total job cash outflow estimate (no revenue), spread over project duration:
        # - COGS cash (includes lease payment if lease)
        # - SG&A/overhead (if provided)
        # - PLUS debt service if financed ownership (cash flow, not P&L)
        total_job_cash = (res["cash_cost_total"] * num_homes) + (sga_per_home * num_homes) + (res.get("printer_debt_service_per_home", 0.0) * num_homes)
        avg_monthly_burn = total_job_cash / project_months

        # Delta display
        if baseline_delta_cash_value is None:
            delta_display = "N/A"
            delta_sub = ""
        else:
            delta_display = fmt_signed_money(baseline_delta_cash_value)
            delta_sub = f"{(baseline_delta_cash_pct or 0.0)*100:.1f}%"

        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric("Total Wall Cost (Cash)", fmt_money(res["cash_cost_total"]), "excl. printer purchase")
        d2.metric(baseline_delta_label, delta_display, delta_sub)
        d3.metric("Peak Cash Required", fmt_money(res["cash_required"]), "proxy: upfront + first ops")
        d4.metric("Monthly Cash Burn (avg.)", fmt_money(avg_monthly_burn), f"~{project_months} months")
        d5.metric("Days/Home", f"{res['days_per_home']:.1f}", "includes setup")

        # Optional clarity line (short + practical)
        if res.get("printer_monthly_payment", 0.0) > 0:
            st.caption(
                f"Printer structure: **{res.get('printer_acquisition_type','')}** | "
                f"Monthly payment: **{fmt_money(res['printer_monthly_payment'])}/mo** | "
                f"Upfront printer cash: **{fmt_money(res.get('printer_upfront_cash', 0.0))}**"
            )

    # ---------------------------------------------------------
    # ROI / PROFIT + CHART (kept close to your current layout)
    # ---------------------------------------------------------
    g1, g2 = st.columns([1, 1])

    with g1:
        with st.container(border=True):
            st.markdown("##### 🏦 ROI & Profit (Cash vs Accounting)")
            sale_price = st.number_input("Target Shell Sale Price ($)", value=int(res['grand_total'] * 1.3), step=1000)

            cash_profit = sale_price - res['cash_cogs_total'] - sga_per_home
            accounting_profit = sale_price - res['grand_total'] - sga_per_home

            net_cash_after_debt = cash_profit - res.get("printer_debt_service_per_home", 0.0)

            c1, c2 = st.columns(2)
            if res.get("printer_debt_service_per_home", 0.0) > 0:
                c1.metric(
                    "Net Cash (after debt service)",
                    fmt_money(net_cash_after_debt),
                    f"{safe_div(net_cash_after_debt, sale_price)*100:.1f}%" if sale_price > 0 else "0%"
                )
            else:
                c1.metric(
                    "Cash Profit (pre D&A)",
                    fmt_money(cash_profit),
                    f"{safe_div(cash_profit, sale_price)*100:.1f}%" if sale_price > 0 else "0%"
                )

            c2.metric(
                "Accounting Profit (EBIT, pre-tax)",
                fmt_money(accounting_profit),
                f"{safe_div(accounting_profit, sale_price)*100:.1f}%" if sale_price > 0 else "0%"
            )

            upfront_cash = res.get("printer_upfront_cash", 0.0)
            basis_profit = net_cash_after_debt if res.get("printer_debt_service_per_home", 0.0) > 0 else cash_profit

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
            st.markdown("##### Cost Components (Accrual Chart)")
            cost_data = pd.DataFrame([
                {"Category": "Material (Cash)", "Cost": res['mat_cost']},
                {"Category": "Labor (Cash)", "Cost": res['labor_cost']},
                {"Category": "Logistics (Cash)", "Cost": res['logistics_cost']},
                {"Category": "BOS (Cash)", "Cost": res['bos_cost']},
                {"Category": "Printer D&A (Non-cash)", "Cost": res['machine_cost']},
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
    with st.expander("📑 Accounting P&L (for CFO/Investors)", expanded=False):
        pnl_df, pnl_metrics = build_pnl_df(res, sale_price, sga_per_home)

        st.caption(
            "Two-column view shown for clarity. **Cash P&L** = operating cash economics (no D&A). "
            "**Accounting P&L** = accrual view (includes D&A). Printer financing payments are cash flow, not P&L expense."
        )

        show_df = pnl_df.copy()
        show_df["Cash P&L"] = show_df["Cash P&L"].map(lambda x: f"${x:,.0f}")
        show_df["Accounting P&L"] = show_df["Accounting P&L"].map(lambda x: f"${x:,.0f}")
        st.dataframe(show_df, use_container_width=True, hide_index=True)

        ebitda_row = pnl_df.loc[pnl_df["Line Item"] == "EBITDA"].iloc[0]
        ebit_row = pnl_df.loc[pnl_df["Line Item"] == "EBIT (Operating Profit)"].iloc[0]

        m1, m2, m3 = st.columns(3)
        m1.metric("Cash COGS (ex D&A)", fmt_money(res["cash_cost_total"]))
        m2.metric("EBITDA", fmt_money(float(ebitda_row["Cash P&L"])))
        m3.metric(
            "EBIT (Cash vs Accrual)",
            f"{fmt_money(float(ebit_row['Cash P&L']))} | {fmt_money(float(ebit_row['Accounting P&L']))}"
        )

        metrics_show = pnl_metrics.copy()
        metrics_show["Cash"] = metrics_show["Cash"].map(lambda x: f"{x*100:.1f}%")
        metrics_show["Accounting"] = metrics_show["Accounting"].map(lambda x: f"{x*100:.1f}%")
        st.dataframe(metrics_show, use_container_width=True, hide_index=True)

        csv_pnl = pnl_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download P&L CSV", csv_pnl, "3dcp_pnl_per_home.csv", "text/csv")

    # Stats Row
    st.markdown("#### ⚙️ Job Stats")
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
    num_alts = st.radio("Add Scenarios:", [1, 2, 3], horizontal=True)
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
            ("BOS", s['res']['bos_cost']),
            ("Printer D&A", s['res']['machine_cost'])
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
        ("Efficiency (OEE)", "%", lambda s: fmt_pct(s['inputs']['efficiency'])),
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


