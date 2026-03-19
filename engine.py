import numpy_financial as npf


def safe_irr(cashflows):
    try:
        irr = npf.irr(cashflows)
        if irr is None:
            return None
        return float(irr)
    except Exception:
        return None


def get_decision(irr_annual_pct):
    if irr_annual_pct is None:
        return "REVIEW"
    if irr_annual_pct >= 25:
        return "GO"
    if irr_annual_pct >= 15:
        return "REVIEW"
    return "NO GO"


def build_model(inputs):
    deal_value = inputs["deal_value"]
    cost_pct = inputs["cost_pct"] / 100.0
    debt_pct = inputs["debt_pct"] / 100.0
    annual_interest_rate = inputs["interest_rate"] / 100.0
    project_months = int(inputs["project_months"])
    dso_days = inputs["dso_days"]
    payment_type = inputs["payment_type"]
    upfront_pct = inputs["upfront_pct"] / 100.0
    progress_pct = inputs["progress_pct"] / 100.0
    cost_timing = inputs["cost_timing"]
    tax_rate = inputs["tax_rate"] / 100.0
    salvage_pct = inputs["salvage_pct"] / 100.0

    total_cost = deal_value * cost_pct
    debt_target = total_cost * debt_pct
    equity = total_cost - debt_target
    salvage_value = deal_value * salvage_pct
    monthly_rate = annual_interest_rate / 12.0
    delay_month = round(dso_days / 30.0)

    upfront_cash = deal_value * upfront_pct if payment_type == "Trả trước" else 0.0
    actual_debt = max(0.0, debt_target - upfront_cash)

    total_months = project_months + delay_month

    revenue = [0.0] * (total_months + 1)
    cost = [0.0] * (total_months + 1)
    interest = [0.0] * (total_months + 1)
    principal = [0.0] * (total_months + 1)
    tax = [0.0] * (total_months + 1)
    salvage = [0.0] * (total_months + 1)
    equity_outflow = [0.0] * (total_months + 1)

    if payment_type == "Trả trước":
        revenue_upfront = deal_value * upfront_pct
        revenue_final = deal_value - revenue_upfront
        revenue[0] += revenue_upfront
        revenue[project_months + delay_month] += revenue_final

    elif payment_type == "Theo tiến độ":
        revenue_progress_total = deal_value * progress_pct
        revenue_final = deal_value - revenue_progress_total
        revenue_progress_per_month = revenue_progress_total / project_months
        for t in range(1, project_months + 1):
            revenue[t] += revenue_progress_per_month
        revenue[project_months + delay_month] += revenue_final

    elif payment_type == "Trả sau":
        revenue[project_months + delay_month] += deal_value

    if cost_timing == "Trả đều":
        cost_per_month = total_cost / project_months
        for t in range(1, project_months + 1):
            cost[t] += cost_per_month
    elif cost_timing == "Trả đầu kỳ":
        cost[0] += total_cost
    elif cost_timing == "Trả cuối kỳ":
        cost[project_months] += total_cost

    interest_per_month = actual_debt * monthly_rate
    for t in range(1, project_months + 1):
        interest[t] += interest_per_month
    principal[project_months] += actual_debt

    salvage[project_months] += salvage_value

    total_revenue = deal_value
    total_interest = sum(interest)
    taxable_profit = total_revenue - total_cost - total_interest + salvage_value
    total_tax = max(0.0, taxable_profit) * tax_rate
    tax[project_months] += total_tax

    equity_outflow[0] = equity

    net_cf = []
    for t in range(total_months + 1):
        cf = (
            revenue[t]
            + salvage[t]
            - cost[t]
            - interest[t]
            - principal[t]
            - tax[t]
            - equity_outflow[t]
        )
        net_cf.append(cf)

    cum_cf = []
    running = 0.0
    for cf in net_cf:
        running += cf
        cum_cf.append(running)

    irr_month = safe_irr(net_cf)
    irr_annual = None
    if irr_month is not None and irr_month > -1:
        irr_annual = ((1 + irr_month) ** 12 - 1) * 100

    payback_month = None
    for i, value in enumerate(cum_cf):
        if value >= 0:
            payback_month = i
            break

    peak_cash_out = abs(min(cum_cf)) if cum_cf else 0.0
    net_cash_t0 = net_cf[0] if net_cf else 0.0
    decision = get_decision(irr_annual)

    return {
        "timeline": list(range(total_months + 1)),
        "revenue": revenue,
        "cost": cost,
        "interest": interest,
        "principal": principal,
        "tax": tax,
        "salvage": salvage,
        "equity_outflow": equity_outflow,
        "net_cf": net_cf,
        "cum_cf": cum_cf,
        "irr_annual": irr_annual,
        "payback_month": payback_month,
        "peak_cash_out": peak_cash_out,
        "net_cash_t0": net_cash_t0,
        "decision": decision,
        "actual_debt": actual_debt,
        "equity": equity,
    }