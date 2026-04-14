# engine.py
import math

EPS = 1e-9
DAY_BASIS = 360.0
DAYS_PER_MONTH = 30.0
MONTHS_PER_YEAR = 12.0


def normalize_cashflows(cashflows, rel_tol=1e-12, abs_tol=1e-9):
    vals = [float(x) for x in cashflows]
    scale = max([abs(v) for v in vals] + [1.0])
    tol = max(abs_tol, scale * rel_tol)
    normalized = [0.0 if abs(v) <= tol else v for v in vals]
    return normalized, tol


def sign_change_count_clean(cashflows):
    vals, _ = normalize_cashflows(cashflows)
    nz = [v for v in vals if v != 0.0]
    if len(nz) < 2:
        return 0
    return sum((a > 0) != (b > 0) for a, b in zip(nz, nz[1:]))


def month_end_day(day_idx):
    if day_idx <= 0:
        return 0
    return int(math.ceil(day_idx / DAYS_PER_MONTH) * DAYS_PER_MONTH)


def monthly_rate_from_annual_pct(annual_pct):
    annual = float(annual_pct) / 100.0
    if annual <= -1:
        return None
    return (1.0 + annual) ** (1.0 / MONTHS_PER_YEAR) - 1.0


def annualize_monthly_rate(monthly_rate):
    if monthly_rate is None:
        return None
    if monthly_rate <= -1:
        return None
    return ((1.0 + monthly_rate) ** MONTHS_PER_YEAR - 1.0) * 100.0


def annualize_monthly_irr(monthly_irr):
    return annualize_monthly_rate(monthly_irr)


def fisher_real_rate_pct(nominal_annual_pct, inflation_annual_pct):
    if nominal_annual_pct is None or inflation_annual_pct is None:
        return None

    nominal = nominal_annual_pct / 100.0
    inflation = inflation_annual_pct / 100.0

    if (1.0 + inflation) <= EPS:
        return None

    return (((1.0 + nominal) / (1.0 + inflation)) - 1.0) * 100.0


def npv_from_points(rate, points):
    if rate <= -1:
        return None
    try:
        log_base = math.log1p(rate)
        return sum(cf * math.exp(-t * log_base) for t, cf in points)
    except Exception:
        return None


def build_rate_grid():
    grid = [
        -0.9999, -0.99, -0.95, -0.90, -0.80, -0.70, -0.60, -0.50,
        -0.40, -0.30, -0.20, -0.10, -0.05, -0.02, 0.0,
    ]
    grid += [i / 100.0 for i in range(1, 101)]
    x = 1.0
    for _ in range(40):
        x = x * 1.25 + 0.01
        grid.append(x)
    return sorted(set(grid))


def bisect_root(points, low, high, tol=1e-8, max_iter=300):
    f_low = npv_from_points(low, points)
    f_high = npv_from_points(high, points)

    if f_low is None or f_high is None:
        return None
    if abs(f_low) <= tol:
        return low
    if abs(f_high) <= tol:
        return high
    if f_low * f_high > 0:
        return None

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        f_mid = npv_from_points(mid, points)
        if f_mid is None:
            return None
        if abs(f_mid) <= tol:
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return (low + high) / 2.0


def solve_all_irrs(cashflows, times):
    vals, _ = normalize_cashflows(cashflows)

    if len(vals) != len(times):
        raise ValueError("times phải có cùng số phần tử với cashflows.")

    points = [(float(t), float(cf)) for t, cf in zip(times, vals) if cf != 0.0]
    if len(points) < 2:
        return []

    has_positive = any(cf > 0 for _, cf in points)
    has_negative = any(cf < 0 for _, cf in points)
    if not (has_positive and has_negative):
        return []

    roots = []
    grid = build_rate_grid()

    for i in range(len(grid) - 1):
        r1 = grid[i]
        r2 = grid[i + 1]
        v1 = npv_from_points(r1, points)
        v2 = npv_from_points(r2, points)

        if v1 is None or v2 is None:
            continue

        if abs(v1) <= 1e-8:
            roots.append(r1)
        if abs(v2) <= 1e-8:
            roots.append(r2)
        if v1 * v2 < 0:
            root = bisect_root(points, r1, r2)
            if root is not None:
                roots.append(root)

    roots = sorted(roots)
    dedup = []
    for root in roots:
        if not dedup or abs(root - dedup[-1]) > 1e-6:
            dedup.append(root)

    return dedup


def reference_monthly_return(cashflows, times):
    vals, _ = normalize_cashflows(cashflows)

    negatives = [(-cf, t) for cf, t in zip(vals, times) if cf < 0]
    positives = [(cf, t) for cf, t in zip(vals, times) if cf > 0]

    if not negatives or not positives:
        return None

    total_neg = sum(v for v, _ in negatives)
    total_pos = sum(v for v, _ in positives)

    avg_out_time = sum(v * t for v, t in negatives) / total_neg
    avg_in_time = sum(v * t for v, t in positives) / total_pos
    duration = max(avg_in_time - avg_out_time, 1e-9)

    if total_neg <= 0 or total_pos <= 0:
        return None

    return (total_pos / total_neg) ** (1.0 / duration) - 1.0


def is_economically_positive(cashflows):
    vals, _ = normalize_cashflows(cashflows)
    total_pos = sum(v for v in vals if v > 0)
    total_neg = -sum(v for v in vals if v < 0)
    return total_pos > total_neg + 1e-9


def choose_financial_irr(roots, cashflows, times):
    if not roots:
        return None, "Không tìm được nghiệm IRR hợp lệ."

    if len(roots) == 1:
        return roots[0], None

    vals, _ = normalize_cashflows(cashflows)
    total_pos = sum(v for v in vals if v > 0)
    total_neg = -sum(v for v in vals if v < 0)
    ref = reference_monthly_return(vals, times)

    prefer_non_negative = total_pos >= total_neg - 1e-9
    preferred = [r for r in roots if r >= 0] if prefer_non_negative else [r for r in roots if r <= 0]
    candidates = preferred or roots

    if ref is None:
        chosen = min(candidates, key=lambda r: abs(r))
    else:
        chosen = min(candidates, key=lambda r: abs(r - ref))

    note = (
        f"Có {len(roots)} nghiệm IRR. "
        f"Đã chọn nghiệm {'không âm' if chosen >= 0 else 'âm'} gần nhất với cấu trúc kinh tế của dòng tiền."
    )
    return chosen, note


def safe_mirr(cashflows, times, finance_annual_pct, reinvest_annual_pct):
    vals, _ = normalize_cashflows(cashflows)

    if len(vals) != len(times):
        raise ValueError("times phải có cùng số phần tử với cashflows.")

    points = [(float(t), float(cf)) for t, cf in zip(times, vals) if cf != 0.0]
    if len(points) < 2:
        return None

    has_positive = any(cf > 0 for _, cf in points)
    has_negative = any(cf < 0 for _, cf in points)
    if not (has_positive and has_negative):
        return None

    finance_rate = monthly_rate_from_annual_pct(finance_annual_pct)
    reinvest_rate = monthly_rate_from_annual_pct(reinvest_annual_pct)

    if finance_rate is None or reinvest_rate is None:
        return None
    if finance_rate <= -1 or reinvest_rate <= -1:
        return None

    horizon = max(t for t, _ in points)
    if horizon <= 0:
        return None

    pv_negative = 0.0
    fv_positive = 0.0

    for t, cf in points:
        if cf < 0:
            pv_negative += cf / ((1.0 + finance_rate) ** t)
        elif cf > 0:
            fv_positive += cf * ((1.0 + reinvest_rate) ** (horizon - t))

    if pv_negative >= -EPS or fv_positive <= EPS:
        return None

    return (fv_positive / (-pv_negative)) ** (1.0 / horizon) - 1.0


def discounted_npv(cashflows, times, annual_discount_rate_pct):
    vals, _ = normalize_cashflows(cashflows)

    if len(vals) != len(times):
        raise ValueError("times phải có cùng số phần tử với cashflows.")

    rate = monthly_rate_from_annual_pct(annual_discount_rate_pct)
    if rate is None or rate <= -1:
        return None

    total = 0.0
    for t, cf in zip(times, vals):
        total += cf / ((1.0 + rate) ** float(t))
    return total


def classify_real_mirr_vs_bank(real_mirr_pct, bank_real_rate_pct):
    if real_mirr_pct is None or bank_real_rate_pct is None:
        return (
            "REVIEW",
            None,
            "Không tính được đầy đủ MIRR vốn chủ thực hoặc lãi suất ngân hàng thực để so sánh theo Fisher.",
        )

    spread = real_mirr_pct - bank_real_rate_pct

    if spread >= 5:
        return (
            "GO",
            spread,
            f"MIRR vốn chủ thực cao hơn lãi suất ngân hàng thực {spread:.2f} điểm %, tạo chênh lệch đủ hấp dẫn.",
        )

    if spread >= 0:
        return (
            "REVIEW",
            spread,
            f"MIRR vốn chủ thực chỉ cao hơn lãi suất ngân hàng thực {spread:.2f} điểm %, chênh lệch dương nhưng còn mỏng.",
        )

    return (
        "NO GO",
        spread,
        f"MIRR vốn chủ thực thấp hơn lãi suất ngân hàng thực {abs(spread):.2f} điểm %, chưa hấp dẫn so với benchmark.",
    )


def classify_npv(npv_value, scale_reference, label):
    if npv_value is None:
        return "REVIEW", f"Không tính được {label}."

    if abs(scale_reference) <= EPS:
        if npv_value > EPS:
            return "GO", f"{label} dương {npv_value:,.0f}, tạo giá trị gia tăng sau chiết khấu theo benchmark."
        if npv_value >= -EPS:
            return "REVIEW", f"{label} xấp xỉ 0, biên an toàn thấp."
        return "NO GO", f"{label} âm {abs(npv_value):,.0f}, giá trị hiện tại thuần không hấp dẫn."

    ratio_pct = npv_value / scale_reference * 100.0

    if npv_value > EPS and ratio_pct >= 5:
        return (
            "GO",
            f"{label} dương {npv_value:,.0f}, tương đương {ratio_pct:.2f}% trên cơ sở vốn tham chiếu, tạo giá trị tốt.",
        )

    if npv_value > EPS:
        return (
            "REVIEW",
            f"{label} dương {npv_value:,.0f}, tương đương {ratio_pct:.2f}% trên cơ sở vốn tham chiếu, có giá trị nhưng chưa dày.",
        )

    if npv_value >= -EPS:
        return "REVIEW", f"{label} xấp xỉ 0, biên an toàn thấp."

    return (
        "NO GO",
        f"{label} âm {abs(npv_value):,.0f}, tương đương {abs(ratio_pct):.2f}% trên cơ sở vốn tham chiếu, chưa tạo giá trị hiện tại thuần.",
    )


def classify_net_profit_margin(net_profit_margin_pct):
    if net_profit_margin_pct is None:
        return "REVIEW", "Không tính được Net Profit Margin."

    if net_profit_margin_pct >= 8:
        return (
            "GO",
            f"Net Profit Margin đạt {net_profit_margin_pct:.2f}%, cho thấy biên lợi nhuận ròng tương đối tốt sau khi đã tính chiết khấu, lãi vay và thuế.",
        )

    if net_profit_margin_pct >= 4:
        return (
            "REVIEW",
            f"Net Profit Margin đạt {net_profit_margin_pct:.2f}%, dương nhưng còn mỏng; cần xem lại độ an toàn của biên lợi nhuận.",
        )

    return (
        "NO GO",
        f"Net Profit Margin chỉ đạt {net_profit_margin_pct:.2f}%, biên lợi nhuận ròng thấp và dễ bị bào mòn nếu phát sinh thêm chi phí hoặc chậm thu tiền.",
    )


def classify_multiple(multiple_value, label):
    if multiple_value is None:
        return "REVIEW", f"Không tính được {label}."

    if multiple_value >= 1.5:
        return (
            "GO",
            f"{label} đạt {multiple_value:.2f}x, cho thấy dòng tiền trả về cho vốn chủ khá tốt so với số vốn đã bơm vào.",
        )

    if multiple_value >= 1.2:
        return (
            "REVIEW",
            f"{label} đạt {multiple_value:.2f}x, có hoàn vốn và có lãi nhưng dư địa chưa thật sự mạnh.",
        )

    return (
        "NO GO",
        f"{label} chỉ đạt {multiple_value:.2f}x, mức thu hồi vốn chủ thấp so với vốn đã bỏ ra.",
    )


def aggregate_decision(mirr_status, npv_status, npm_status, multiple_status):
    critical = [mirr_status, npv_status]
    support = [npm_status, multiple_status]

    if critical.count("NO GO") >= 2:
        return "NO GO"

    if "NO GO" in critical and "NO GO" in support:
        return "NO GO"

    if critical.count("GO") == 2 and all(x != "NO GO" for x in support):
        return "GO"

    if support.count("NO GO") >= 2:
        return "NO GO"

    return "REVIEW"


def build_model(inputs):
    gross_deal_value = float(inputs["deal_value"])
    contract_discount_pct = float(inputs.get("contract_discount_pct", 0.0)) / 100.0
    cost_pct = float(inputs["cost_pct"]) / 100.0
    salvage_pct = float(inputs.get("salvage_pct", 0.0)) / 100.0
    cit_rate = float(inputs.get("tax_rate", 0.0)) / 100.0
    avg_dso_days = int(inputs.get("avg_dso_days", 0))

    owner_advance_pct = float(inputs.get("owner_advance_pct", 0.0)) / 100.0
    interest_rate_pct_input = float(inputs.get("interest_rate", 0.0))
    interest_rate_annual = interest_rate_pct_input / 100.0
    bank_rate_pct = float(inputs.get("bank_rate_pct", 0.0))
    inflation_rate_pct = float(inputs.get("inflation_rate_pct", 0.0))
    principal_repayment_mode = str(inputs.get("principal_repayment_mode", "Trả định kỳ theo tháng"))
    after_sales_pct = float(inputs.get("after_sales_pct", 0.0)) / 100.0
    warranty_days = int(inputs.get("warranty_days", 0))

    raw_stages = inputs.get("stages", [])
    raw_debt_draw_schedule = inputs.get("debt_draw_schedule", [])

    if gross_deal_value <= 0:
        raise ValueError("Giá trị hợp đồng phải lớn hơn 0.")
    if not (0 <= contract_discount_pct <= 1):
        raise ValueError("Chiết khấu hợp đồng phải nằm trong khoảng 0% đến 100%.")
    if not (0 <= cost_pct <= 1):
        raise ValueError("Tỷ lệ giá vốn phải nằm trong khoảng 0% đến 100%.")
    if not (0 <= salvage_pct <= 1):
        raise ValueError("Giá trị thu hồi cuối kỳ phải nằm trong khoảng 0% đến 100%.")
    if not (0 <= cit_rate <= 1):
        raise ValueError("Thuế CIT phải nằm trong khoảng 0% đến 100%.")
    if not (0 <= owner_advance_pct <= 1):
        raise ValueError("Tỷ lệ tạm ứng CĐT phải nằm trong khoảng 0% đến 100% giá trị hợp đồng sau chiết khấu.")
    if not (0 <= after_sales_pct <= 1):
        raise ValueError("Tỷ lệ bảo hành / bảo hiểm hậu mãi phải nằm trong khoảng 0% đến 100% giá trị hợp đồng.")
    if not (0 <= bank_rate_pct <= 100):
        raise ValueError("Lãi suất ngân hàng benchmark phải nằm trong khoảng 0% đến 100%.")
    if not (0 <= inflation_rate_pct <= 100):
        raise ValueError("Lạm phát phải nằm trong khoảng 0% đến 100%.")
    if avg_dso_days < 0:
        raise ValueError("Số ngày công nợ trung bình không được âm.")
    if warranty_days < 0:
        raise ValueError("Thời hạn bảo hành không được âm.")

    valid_principal_modes = {
        "Trả định kỳ theo tháng",
        "Trả hết một lần ở ngày cuối cùng của tháng cuối cùng của giai đoạn thanh toán cuối cùng",
    }
    if principal_repayment_mode not in valid_principal_modes:
        raise ValueError("Phương thức trả gốc vay không hợp lệ.")

    stages = []
    for s in raw_stages:
        duration_days = int(s["duration_days"])
        payment_pct = float(s["payment_pct"])
        cost_out_pct = float(s["cost_out_pct"])
        name = str(s.get("name", f"Giai đoạn {len(stages) + 1}")).strip() or f"Giai đoạn {len(stages) + 1}"

        if duration_days <= 0:
            raise ValueError(f"{name}: thời lượng giai đoạn phải lớn hơn 0 ngày.")
        if payment_pct <= 0:
            raise ValueError(f"{name}: tỷ lệ thanh toán phải lớn hơn 0.")
        if cost_out_pct <= 0:
            raise ValueError(f"{name}: tỷ lệ chi tiền đầu giai đoạn phải lớn hơn 0.")

        stages.append(
            {
                "stage_no": len(stages) + 1,
                "name": name,
                "duration_days": duration_days,
                "payment_pct": payment_pct,
                "cost_out_pct": cost_out_pct,
            }
        )

    if not stages:
        raise ValueError("Phải có ít nhất 1 giai đoạn nghiệm thu.")
    if len(stages) > 5:
        raise ValueError("Tối đa 5 giai đoạn nghiệm thu.")

    total_stage_payment_pct = sum(s["payment_pct"] for s in stages)
    total_customer_payment_pct = owner_advance_pct * 100.0 + total_stage_payment_pct
    if abs(total_customer_payment_pct - 100.0) > 1e-6:
        raise ValueError(
            "Tỷ lệ tạm ứng CĐT ban đầu + tổng tỷ lệ thanh toán các giai đoạn phải bằng đúng 100% giá trị hợp đồng sau chiết khấu."
        )

    total_cost_out_pct = sum(s["cost_out_pct"] for s in stages)
    if abs(total_cost_out_pct - 100.0) > 1e-6:
        raise ValueError("Tổng tỷ lệ chi tiền đầu các giai đoạn phải bằng đúng 100% giá vốn.")

    contract_discount_amount = gross_deal_value * contract_discount_pct
    net_contract_value = gross_deal_value - contract_discount_amount

    total_cost = gross_deal_value * cost_pct
    salvage_value_total = gross_deal_value * salvage_pct
    owner_advance_amount = net_contract_value * owner_advance_pct
    after_sales_total = gross_deal_value * after_sales_pct

    daily_interest_rate = interest_rate_annual / DAY_BASIS

    stage_plan = []
    day_cursor = 1

    for s in stages:
        start_day = day_cursor
        end_day = start_day + s["duration_days"] - 1
        collection_day = end_day + avg_dso_days

        revenue_share = s["payment_pct"] / total_stage_payment_pct
        gross_contract_billing_value = gross_deal_value * revenue_share
        stage_discount_amount = contract_discount_amount * revenue_share
        net_stage_billing_value = net_contract_value * revenue_share
        advance_offset = owner_advance_amount * revenue_share
        net_collection_value = net_stage_billing_value - advance_offset
        stage_cost = total_cost * (s["cost_out_pct"] / 100.0)

        stage_plan.append(
            {
                "stage_no": s["stage_no"],
                "name": s["name"],
                "duration_days": s["duration_days"],
                "start_day": start_day,
                "end_day": end_day,
                "collection_day": collection_day,
                "payment_pct": s["payment_pct"],
                "cost_out_pct": s["cost_out_pct"],
                "revenue_share_pct": revenue_share * 100.0,
                "gross_contract_billing_value": gross_contract_billing_value,
                "stage_discount_amount": stage_discount_amount,
                "net_stage_billing_value": net_stage_billing_value,
                "advance_offset": advance_offset,
                "net_collection_value": net_collection_value,
                "stage_cost": stage_cost,
                "customer_cash_used_for_stage_cost": 0.0,
                "actual_debt_draw": 0.0,
                "actual_equity_for_stage_cost": 0.0,
            }
        )
        day_cursor = end_day + 1

    last_stage_end = stage_plan[-1]["end_day"]
    last_collection_day = max(x["collection_day"] for x in stage_plan)
    last_payment_day = month_end_day(last_collection_day)

    if after_sales_total > 0 and warranty_days > 0:
        after_sales_start_day = last_stage_end + 1
        after_sales_end_day = last_stage_end + warranty_days
    else:
        after_sales_start_day = last_stage_end
        after_sales_end_day = last_stage_end

    horizon = max(last_payment_day, after_sales_end_day)
    timeline = list(range(horizon + 1))
    time_in_months = [t / DAYS_PER_MONTH for t in timeline]

    customer_advance = [0.0] * (horizon + 1)
    billing_gross = [0.0] * (horizon + 1)
    billing_discount = [0.0] * (horizon + 1)
    billing_net = [0.0] * (horizon + 1)
    net_billing = [0.0] * (horizon + 1)
    collections = [0.0] * (horizon + 1)
    cost = [0.0] * (horizon + 1)
    after_sales = [0.0] * (horizon + 1)
    salvage = [0.0] * (horizon + 1)
    project_tax = [0.0] * (horizon + 1)

    customer_advance[0] = owner_advance_amount

    for stage in stage_plan:
        billing_gross[stage["end_day"]] += stage["gross_contract_billing_value"]
        billing_discount[stage["end_day"]] += stage["stage_discount_amount"]
        billing_net[stage["end_day"]] += stage["net_stage_billing_value"]
        net_billing[stage["end_day"]] += stage["net_stage_billing_value"]
        collections[stage["collection_day"]] += stage["net_collection_value"]

    for stage in stage_plan:
        cost[stage["start_day"]] += stage["stage_cost"]

    allocated_cost = sum(cost)
    residual_cost = total_cost - allocated_cost
    if abs(residual_cost) > EPS:
        cost[stage_plan[-1]["start_day"]] += residual_cost
        stage_plan[-1]["stage_cost"] += residual_cost

    if after_sales_total > 0:
        if warranty_days > 0:
            daily_after_sales = after_sales_total / warranty_days
            for t in range(after_sales_start_day, after_sales_end_day + 1):
                after_sales[t] += daily_after_sales
        else:
            after_sales[last_stage_end] += after_sales_total

    salvage[horizon] += salvage_value_total

    debt_limit_amount_by_stage = {i: 0.0 for i in range(1, len(stage_plan) + 1)}
    for item in raw_debt_draw_schedule:
        stage_no = int(item["stage_no"])
        draw_pct_cost = float(item["draw_pct_cost"])

        if draw_pct_cost < 0:
            raise ValueError(f"Hạn mức vay giai đoạn {stage_no} không được âm.")
        if stage_no < 1 or stage_no > len(stage_plan):
            raise ValueError("Hạn mức vay chỉ được phép trong các giai đoạn đã khai báo.")

        debt_limit_amount_by_stage[stage_no] += total_cost * (draw_pct_cost / 100.0)

    total_debt_limit_amount = sum(debt_limit_amount_by_stage.values())
    if total_debt_limit_amount - total_cost > EPS:
        raise ValueError("Tổng hạn mức vay không được lớn hơn tổng giá vốn.")

    stage_by_start_day = {stage["start_day"]: stage for stage in stage_plan}
    monthly_payment_days = set(range(30, int(last_payment_day) + 1, 30))

    def calc_principal_due(day_idx, current_debt_balance):
        if current_debt_balance <= EPS:
            return 0.0

        if principal_repayment_mode == "Trả định kỳ theo tháng":
            if day_idx in monthly_payment_days:
                remaining_payment_days = [d for d in monthly_payment_days if d >= day_idx]
                if remaining_payment_days:
                    return current_debt_balance / len(remaining_payment_days)
            return 0.0

        if principal_repayment_mode == "Trả hết một lần ở ngày cuối cùng của tháng cuối cùng của giai đoạn thanh toán cuối cùng":
            if day_idx == last_payment_day:
                return current_debt_balance
            return 0.0

        return 0.0

    def run_waterfall(total_tax_at_horizon):
        debt_draw_local = [0.0] * (horizon + 1)
        interest_local = [0.0] * (horizon + 1)
        principal_local = [0.0] * (horizon + 1)
        tax_local = [0.0] * (horizon + 1)
        equity_in_local = [0.0] * (horizon + 1)
        equity_out_local = [0.0] * (horizon + 1)
        opening_cash_local = [0.0] * (horizon + 1)
        closing_cash_local = [0.0] * (horizon + 1)
        debt_balance_series_local = [0.0] * (horizon + 1)

        reserve_required_local = [0.0] * (horizon + 1)
        excess_cash_distributed_local = [0.0] * (horizon + 1)

        stage_cash_used_map = {stage["stage_no"]: 0.0 for stage in stage_plan}
        stage_debt_used_map = {stage["stage_no"]: 0.0 for stage in stage_plan}
        stage_equity_used_map = {stage["stage_no"]: 0.0 for stage in stage_plan}

        tax_local[horizon] = total_tax_at_horizon

        cash_balance = 0.0
        debt_balance = 0.0
        peak_debt_local = 0.0

        def simulate_forward_no_distribution(start_day, starting_cash, starting_debt):
            sim_cash = float(starting_cash)
            sim_debt = float(starting_debt)
            future_equity_needed = 0.0

            for tt in range(start_day, horizon + 1):
                sim_cash += customer_advance[tt] + collections[tt] + salvage[tt]

                if tt in stage_by_start_day:
                    sim_stage = stage_by_start_day[tt]
                    sim_stage_cost = sim_stage["stage_cost"]

                    sim_cash_used = min(sim_cash, sim_stage_cost)
                    sim_cash -= sim_cash_used
                    sim_remaining_stage_cost = sim_stage_cost - sim_cash_used

                    sim_stage_debt_limit = debt_limit_amount_by_stage.get(sim_stage["stage_no"], 0.0)
                    sim_debt_used = min(sim_remaining_stage_cost, sim_stage_debt_limit)
                    if sim_debt_used > EPS:
                        sim_debt += sim_debt_used
                        sim_remaining_stage_cost -= sim_debt_used

                    if sim_remaining_stage_cost > EPS:
                        future_equity_needed += sim_remaining_stage_cost

                sim_interest_due = sim_debt * daily_interest_rate if sim_debt > EPS else 0.0
                sim_principal_due = calc_principal_due(tt, sim_debt)
                sim_other_outflows = after_sales[tt] + sim_interest_due + tax_local[tt] + sim_principal_due

                if sim_cash >= sim_other_outflows:
                    sim_cash -= sim_other_outflows
                else:
                    sim_shortage = sim_other_outflows - sim_cash
                    future_equity_needed += sim_shortage
                    sim_cash = 0.0

                if sim_principal_due > EPS:
                    sim_debt -= sim_principal_due
                    if sim_debt < EPS:
                        sim_debt = 0.0

                if tt == horizon and sim_debt > EPS:
                    future_equity_needed += sim_debt
                    sim_debt = 0.0

            return future_equity_needed

        reserve_cache = {}

        def required_cash_reserve_from_next_day(next_day, current_debt_balance):
            if next_day > horizon:
                return 0.0

            cache_key = (next_day, round(current_debt_balance, 8))
            if cache_key in reserve_cache:
                return reserve_cache[cache_key]

            equity_need_at_zero_cash = simulate_forward_no_distribution(
                start_day=next_day,
                starting_cash=0.0,
                starting_debt=current_debt_balance,
            )

            if equity_need_at_zero_cash <= EPS:
                reserve_cache[cache_key] = 0.0
                return 0.0

            lo = 0.0
            hi = equity_need_at_zero_cash

            for _ in range(60):
                mid = (lo + hi) / 2.0
                future_equity_needed = simulate_forward_no_distribution(
                    start_day=next_day,
                    starting_cash=mid,
                    starting_debt=current_debt_balance,
                )
                if future_equity_needed <= EPS:
                    hi = mid
                else:
                    lo = mid

            reserve_cache[cache_key] = hi
            return hi

        distribution_days = {0, horizon}
        distribution_days.update(t for t, x in enumerate(collections) if abs(x) > EPS)
        distribution_days.update(t for t, x in enumerate(customer_advance) if abs(x) > EPS)
        distribution_days.update(t for t, x in enumerate(salvage) if abs(x) > EPS)

        for t in timeline:
            opening_cash_local[t] = cash_balance
            cash_balance += customer_advance[t] + collections[t] + salvage[t]

            if t in stage_by_start_day:
                stage = stage_by_start_day[t]
                stage_no = stage["stage_no"]
                stage_cost = stage["stage_cost"]

                cash_used = min(cash_balance, stage_cost)
                cash_balance -= cash_used
                remaining_stage_cost = stage_cost - cash_used

                stage_debt_limit = debt_limit_amount_by_stage.get(stage_no, 0.0)
                debt_used = min(remaining_stage_cost, stage_debt_limit)
                if debt_used > EPS:
                    debt_draw_local[t] += debt_used
                    debt_balance += debt_used
                    remaining_stage_cost -= debt_used

                equity_used_for_stage = 0.0
                if remaining_stage_cost > EPS:
                    equity_used_for_stage = remaining_stage_cost
                    equity_in_local[t] += equity_used_for_stage

                stage_cash_used_map[stage_no] = cash_used
                stage_debt_used_map[stage_no] = debt_used
                stage_equity_used_map[stage_no] = equity_used_for_stage

            peak_debt_local = max(peak_debt_local, debt_balance)

            interest_due = debt_balance * daily_interest_rate if debt_balance > EPS else 0.0
            interest_local[t] = interest_due

            principal_due = calc_principal_due(t, debt_balance)
            other_outflows = after_sales[t] + interest_due + tax_local[t] + principal_due

            if cash_balance >= other_outflows:
                cash_balance -= other_outflows
            else:
                shortage = other_outflows - cash_balance
                cash_balance = 0.0
                equity_in_local[t] += shortage

            if principal_due > EPS:
                debt_balance -= principal_due
                if debt_balance < EPS:
                    debt_balance = 0.0
                principal_local[t] = principal_due

            if t == horizon and debt_balance > EPS:
                equity_in_local[t] += debt_balance
                principal_local[t] += debt_balance
                debt_balance = 0.0

            if t in distribution_days and t < horizon and cash_balance > EPS:
                reserve_needed = required_cash_reserve_from_next_day(
                    next_day=t + 1,
                    current_debt_balance=debt_balance,
                )
            else:
                reserve_needed = 0.0

            reserve_required_local[t] = reserve_needed

            distributable_cash = max(0.0, cash_balance - reserve_needed)
            if distributable_cash > EPS:
                equity_out_local[t] = distributable_cash
                excess_cash_distributed_local[t] = distributable_cash
                cash_balance -= distributable_cash

            debt_balance_series_local[t] = debt_balance
            closing_cash_local[t] = cash_balance

        total_interest_local = sum(interest_local)

        return {
            "debt_draw": debt_draw_local,
            "interest": interest_local,
            "principal": principal_local,
            "tax": tax_local,
            "equity_in": equity_in_local,
            "equity_out": equity_out_local,
            "opening_cash": opening_cash_local,
            "closing_cash": closing_cash_local,
            "debt_balance": debt_balance_series_local,
            "peak_debt": peak_debt_local,
            "total_interest": total_interest_local,
            "stage_cash_used_map": stage_cash_used_map,
            "stage_debt_used_map": stage_debt_used_map,
            "stage_equity_used_map": stage_equity_used_map,
            "reserve_required": reserve_required_local,
            "excess_cash_distributed": excess_cash_distributed_local,
        }

    pass1 = run_waterfall(total_tax_at_horizon=0.0)
    total_interest_pass1 = pass1["total_interest"]

    pre_tax_profit_equity = net_contract_value + salvage_value_total - total_cost - after_sales_total - total_interest_pass1
    total_cit = max(0.0, pre_tax_profit_equity) * cit_rate

    pre_tax_profit_project = net_contract_value + salvage_value_total - total_cost - after_sales_total
    project_tax_total = max(0.0, pre_tax_profit_project) * cit_rate
    project_tax[horizon] = project_tax_total

    pass2 = run_waterfall(total_tax_at_horizon=total_cit)

    debt_draw = pass2["debt_draw"]
    interest = pass2["interest"]
    principal = pass2["principal"]
    tax = pass2["tax"]
    equity_in = pass2["equity_in"]
    equity_out = pass2["equity_out"]
    opening_cash = pass2["opening_cash"]
    closing_cash = pass2["closing_cash"]
    debt_balance_series = pass2["debt_balance"]
    peak_debt = pass2["peak_debt"]
    total_interest = pass2["total_interest"]
    reserve_required = pass2["reserve_required"]
    excess_cash_distributed = pass2["excess_cash_distributed"]

    for stage in stage_plan:
        stage_no = stage["stage_no"]
        stage["customer_cash_used_for_stage_cost"] = pass2["stage_cash_used_map"][stage_no]
        stage["actual_debt_draw"] = pass2["stage_debt_used_map"][stage_no]
        stage["actual_equity_for_stage_cost"] = pass2["stage_equity_used_map"][stage_no]

    total_actual_debt_draw = sum(debt_draw)

    ar_balance = [0.0] * (horizon + 1)
    project_cf = [0.0] * (horizon + 1)
    equity_cf = [0.0] * (horizon + 1)

    running_ar = 0.0
    for t in timeline:
        running_ar += net_billing[t] - collections[t]
        ar_balance[t] = running_ar

        project_cf[t] = (
            customer_advance[t]
            + collections[t]
            + salvage[t]
            - cost[t]
            - after_sales[t]
            - project_tax[t]
        )

        equity_cf[t] = -equity_in[t] + equity_out[t]

    project_cf_sign_changes = sign_change_count_clean(project_cf)
    equity_cf_sign_changes = sign_change_count_clean(equity_cf)

    project_irr_roots = solve_all_irrs(project_cf, time_in_months)
    equity_irr_roots = solve_all_irrs(equity_cf, time_in_months)

    project_irr_monthly, project_irr_selection_note = choose_financial_irr(
        project_irr_roots,
        project_cf,
        time_in_months,
    )
    equity_irr_monthly, equity_irr_selection_note = choose_financial_irr(
        equity_irr_roots,
        equity_cf,
        time_in_months,
    )

    project_irr_warning = None
    equity_irr_warning = None

    if project_cf_sign_changes > 1:
        project_irr_warning = (
            f"Project cash flow đổi dấu {project_cf_sign_changes} lần; "
            "IRR có thể không duy nhất. Hệ thống đã chọn nghiệm tài chính phù hợp nhất."
        )
    if equity_cf_sign_changes > 1:
        equity_irr_warning = (
            f"Equity cash flow đổi dấu {equity_cf_sign_changes} lần; "
            "IRR có thể không duy nhất. Hệ thống đã chọn nghiệm tài chính phù hợp nhất."
        )

    if project_irr_selection_note:
        project_irr_warning = (
            f"{project_irr_warning} {project_irr_selection_note}".strip()
            if project_irr_warning
            else project_irr_selection_note
        )
    if equity_irr_selection_note:
        equity_irr_warning = (
            f"{equity_irr_warning} {equity_irr_selection_note}".strip()
            if equity_irr_warning
            else equity_irr_selection_note
        )

    if project_irr_monthly is not None and project_irr_monthly < 0 and is_economically_positive(project_cf):
        non_negative_roots = [r for r in project_irr_roots if r >= 0]
        if non_negative_roots:
            ref = reference_monthly_return(project_cf, time_in_months) or 0.0
            project_irr_monthly = min(non_negative_roots, key=lambda r: abs(r - ref))
            project_irr_warning = (
                f"{project_irr_warning} Đã loại nghiệm âm bất thường và chuyển sang nghiệm không âm hợp lý hơn."
                if project_irr_warning
                else "Đã loại nghiệm âm bất thường và chuyển sang nghiệm không âm hợp lý hơn."
            )

    if equity_irr_monthly is not None and equity_irr_monthly < 0 and is_economically_positive(equity_cf):
        non_negative_roots = [r for r in equity_irr_roots if r >= 0]
        if non_negative_roots:
            ref = reference_monthly_return(equity_cf, time_in_months) or 0.0
            equity_irr_monthly = min(non_negative_roots, key=lambda r: abs(r - ref))
            equity_irr_warning = (
                f"{equity_irr_warning} Đã loại nghiệm âm bất thường và chuyển sang nghiệm không âm hợp lý hơn."
                if equity_irr_warning
                else "Đã loại nghiệm âm bất thường và chuyển sang nghiệm không âm hợp lý hơn."
            )

    project_irr_annual = annualize_monthly_irr(project_irr_monthly)
    equity_irr_annual = annualize_monthly_irr(equity_irr_monthly)

    project_real_irr_annual = fisher_real_rate_pct(project_irr_annual, inflation_rate_pct)
    equity_real_irr_annual = fisher_real_rate_pct(equity_irr_annual, inflation_rate_pct)
    bank_real_rate_annual = fisher_real_rate_pct(bank_rate_pct, inflation_rate_pct)

    project_mirr_monthly = safe_mirr(project_cf, time_in_months, interest_rate_pct_input, bank_rate_pct)
    equity_mirr_monthly = safe_mirr(equity_cf, time_in_months, interest_rate_pct_input, bank_rate_pct)
    project_mirr_annual = annualize_monthly_rate(project_mirr_monthly)
    equity_mirr_annual = annualize_monthly_rate(equity_mirr_monthly)
    project_real_mirr_annual = fisher_real_rate_pct(project_mirr_annual, inflation_rate_pct)
    equity_real_mirr_annual = fisher_real_rate_pct(equity_mirr_annual, inflation_rate_pct)

    real_mirr_status, real_mirr_spread_vs_bank, real_mirr_explanation = classify_real_mirr_vs_bank(
        equity_real_mirr_annual,
        bank_real_rate_annual,
    )

    project_npv = discounted_npv(project_cf, time_in_months, bank_rate_pct)
    equity_npv = discounted_npv(equity_cf, time_in_months, bank_rate_pct)

    cum_equity_cf = []
    running_cum_equity_cf = 0.0
    for x in equity_cf:
        running_cum_equity_cf += x
        cum_equity_cf.append(running_cum_equity_cf)

    total_equity_in = sum(equity_in)
    total_equity_out = sum(equity_out)

    running_equity_at_risk = 0.0
    peak_equity_at_risk = 0.0
    payback_day = None
    has_called_equity = False

    for t in timeline:
        if equity_in[t] > EPS:
            has_called_equity = True

        running_equity_at_risk += equity_in[t] - equity_out[t]
        peak_equity_at_risk = max(peak_equity_at_risk, running_equity_at_risk)

        if has_called_equity and running_equity_at_risk <= EPS and payback_day is None:
            payback_day = t

    if total_equity_in <= EPS:
        payback_day = 0
        payback_message = "Mô hình không cần bơm vốn chủ, nên thời gian hoàn vốn được xem là 0 ngày."
    elif payback_day is None:
        payback_message = "Chưa hoàn vốn trong toàn bộ timeline của mô hình."
    else:
        payback_message = f"Hoàn vốn sau {payback_day} ngày."

    equity_multiple = None
    if total_equity_in > EPS:
        equity_multiple = total_equity_out / total_equity_in

    moic = equity_multiple

    net_profit = net_contract_value + salvage_value_total - total_cost - after_sales_total - total_interest - total_cit
    net_profit_for_margin = net_contract_value - total_cost - after_sales_total - total_interest - total_cit
    net_profit_margin = None
    if net_contract_value > EPS:
        net_profit_margin = (net_profit_for_margin / net_contract_value) * 100.0

    npv_reference_scale = total_equity_in if total_equity_in > EPS else max(peak_equity_at_risk, net_contract_value, 1.0)
    npv_status, npv_explanation = classify_npv(equity_npv, npv_reference_scale, "NPV vốn chủ")
    net_profit_margin_status, net_profit_margin_explanation = classify_net_profit_margin(net_profit_margin)
    moic_status, moic_explanation = classify_multiple(moic, "MOIC")
    equity_multiple_status, equity_multiple_explanation = classify_multiple(equity_multiple, "Equity Multiple")

    decision = aggregate_decision(real_mirr_status, npv_status, net_profit_margin_status, moic_status)

    decision_basis = (
        "Đánh giá sơ bộ hiện dựa trên 4 lớp: "
        "(1) MIRR vốn chủ thực theo Fisher so với lãi suất ngân hàng thực; "
        "(2) NPV vốn chủ chiết khấu theo lãi suất ngân hàng benchmark; "
        "(3) Net Profit Margin; "
        "(4) MOIC/Equity Multiple. "
        "IRR chỉ dùng để hiển thị tham khảo, không còn dùng để chấm GO/REVIEW/NO GO."
    )

    fisher_basis = (
        "Các chỉ số thực được quy đổi theo Fisher: "
        "real = ((1 + nominal) / (1 + inflation)) - 1. "
        "Việc đánh giá ưu tiên nhìn trên sức sinh lời thực sau khi loại ảnh hưởng của lạm phát."
    )

    irr_basis = (
        "IRR được tính theo hệ quy chiếu tháng lẻ: mỗi mốc thời gian được đổi thành số tháng bằng ngày/30. "
        "Hệ thống quét nhiều khoảng lãi suất, tìm tất cả nghiệm khả dĩ rồi chọn nghiệm tài chính phù hợp nhất."
    )

    mirr_basis = (
        "MIRR được tính trên cùng trục thời gian tháng lẻ. "
        "Dòng tiền âm được chiết khấu theo finance rate và dòng tiền dương được tái đầu tư theo benchmark, "
        "sau đó annualize theo hệ tháng."
    )

    npv_basis = (
        "NPV được tính bằng cách chiết khấu dòng tiền theo lãi suất ngân hàng benchmark năm, "
        "quy đổi sang suất chiết khấu tháng hiệu dụng để phù hợp với trục thời gian tháng lẻ."
    )

    net_profit_margin_basis = (
        "Net Profit Margin = Lợi nhuận ròng từ hoạt động hợp đồng / Giá trị hợp đồng sau chiết khấu. "
        "Khi tính margin đã loại phần salvage khỏi tử số để tránh làm đẹp giả biên lợi nhuận ròng của hoạt động chính."
    )

    multiple_basis = (
        "MOIC và Equity Multiple trong mô hình hiện tại dùng cùng cơ sở: "
        "Tổng tiền trả về cho vốn chủ / Tổng vốn chủ đã bơm vào. "
        "Vì vậy hai chỉ số đang cho cùng giá trị."
    )

    source_of_funds_basis = (
        "Logic tài trợ chi đầu giai đoạn: dùng tiền sẵn có/CĐT trước, "
        "phần thiếu mới rút vay của đúng giai đoạn đó, phần thiếu còn lại mới dùng VCSH."
    )

    if principal_repayment_mode == "Trả định kỳ theo tháng":
        principal_repayment_basis = (
            "Trả gốc vay theo chu kỳ cuối tháng 30 ngày của mô hình. "
            "Tại mỗi cuối tháng, số gốc phải trả được phân bổ đều trên số kỳ cuối tháng còn lại đến tháng thanh toán cuối."
        )
    else:
        principal_repayment_basis = (
            "Trả toàn bộ gốc vay tại ngày cuối cùng của tháng cuối cùng chứa kỳ thanh toán cuối của dự án."
        )

    interest_basis = (
        "Lãi vay được tính theo ngày trên dư nợ sau rút vay của chính ngày đó, với quy ước lãi suất năm/360. "
        "Nhờ vậy cách ghi nhận rút vay, lãi vay và trả gốc trong mô hình là nhất quán trên cùng một timeline."
    )

    evaluation_table = [
        {
            "Nhóm đánh giá": "MIRR thực vs lãi suất NH thực",
            "Kết quả": real_mirr_status,
            "Diễn giải": real_mirr_explanation,
        },
        {
            "Nhóm đánh giá": "NPV vốn chủ",
            "Kết quả": npv_status,
            "Diễn giải": npv_explanation,
        },
        {
            "Nhóm đánh giá": "Net Profit Margin",
            "Kết quả": net_profit_margin_status,
            "Diễn giải": net_profit_margin_explanation,
        },
        {
            "Nhóm đánh giá": "MOIC / Equity Multiple",
            "Kết quả": moic_status,
            "Diễn giải": moic_explanation,
        },
    ]

    return {
        "timeline": timeline,
        "time_in_months": time_in_months,
        "stage_plan": stage_plan,
        "customer_advance": customer_advance,
        "billing_gross": billing_gross,
        "billing_discount": billing_discount,
        "billing_net": billing_net,
        "net_billing": net_billing,
        "collections": collections,
        "ar_balance": ar_balance,
        "cost": cost,
        "after_sales": after_sales,
        "interest": interest,
        "principal": principal,
        "tax": tax,
        "project_tax": project_tax,
        "salvage": salvage,
        "debt_draw": debt_draw,
        "debt_balance": debt_balance_series,
        "equity_in": equity_in,
        "equity_out": equity_out,
        "equity_cf": equity_cf,
        "cum_equity_cf": cum_equity_cf,
        "opening_cash": opening_cash,
        "closing_cash": closing_cash,
        "reserve_required": reserve_required,
        "excess_cash_distributed": excess_cash_distributed,
        "project_cf": project_cf,
        "project_cf_sign_changes": project_cf_sign_changes,
        "equity_cf_sign_changes": equity_cf_sign_changes,
        "project_irr_roots": project_irr_roots,
        "equity_irr_roots": equity_irr_roots,
        "project_irr_warning": project_irr_warning,
        "equity_irr_warning": equity_irr_warning,
        "project_irr_monthly": None if project_irr_monthly is None else project_irr_monthly * 100.0,
        "equity_irr_monthly": None if equity_irr_monthly is None else equity_irr_monthly * 100.0,
        "project_irr_annual": project_irr_annual,
        "equity_irr_annual": equity_irr_annual,
        "project_real_irr_annual": project_real_irr_annual,
        "equity_real_irr_annual": equity_real_irr_annual,
        "project_mirr_monthly": None if project_mirr_monthly is None else project_mirr_monthly * 100.0,
        "equity_mirr_monthly": None if equity_mirr_monthly is None else equity_mirr_monthly * 100.0,
        "project_mirr_annual": project_mirr_annual,
        "equity_mirr_annual": equity_mirr_annual,
        "project_real_mirr_annual": project_real_mirr_annual,
        "equity_real_mirr_annual": equity_real_mirr_annual,
        "bank_real_rate_annual": bank_real_rate_annual,
        "real_mirr_spread_vs_bank": real_mirr_spread_vs_bank,
        "project_npv": project_npv,
        "equity_npv": equity_npv,
        "equity_multiple": equity_multiple,
        "moic": moic,
        "net_profit": net_profit,
        "net_profit_for_margin": net_profit_for_margin,
        "net_profit_margin": net_profit_margin,
        "payback_day": payback_day,
        "payback_message": payback_message,
        "peak_debt": peak_debt,
        "peak_equity_at_risk": peak_equity_at_risk,
        "decision": decision,
        "decision_basis": decision_basis,
        "fisher_basis": fisher_basis,
        "irr_basis": irr_basis,
        "mirr_basis": mirr_basis,
        "npv_basis": npv_basis,
        "net_profit_margin_basis": net_profit_margin_basis,
        "multiple_basis": multiple_basis,
        "source_of_funds_basis": source_of_funds_basis,
        "principal_repayment_basis": principal_repayment_basis,
        "interest_basis": interest_basis,
        "real_mirr_status": real_mirr_status,
        "npv_status": npv_status,
        "net_profit_margin_status": net_profit_margin_status,
        "moic_status": moic_status,
        "equity_multiple_status": equity_multiple_status,
        "real_mirr_explanation": real_mirr_explanation,
        "npv_explanation": npv_explanation,
        "net_profit_margin_explanation": net_profit_margin_explanation,
        "moic_explanation": moic_explanation,
        "equity_multiple_explanation": equity_multiple_explanation,
        "evaluation_table": evaluation_table,
        "gross_deal_value": gross_deal_value,
        "contract_discount_pct": contract_discount_pct * 100.0,
        "contract_discount_amount": contract_discount_amount,
        "net_contract_value": net_contract_value,
        "deal_value": gross_deal_value,
        "total_cost": total_cost,
        "owner_advance_amount": owner_advance_amount,
        "after_sales_total": after_sales_total,
        "salvage_value_total": salvage_value_total,
        "total_interest": total_interest,
        "total_cit": total_cit,
        "project_tax_total": project_tax_total,
        "total_equity_in": total_equity_in,
        "total_equity_out": total_equity_out,
        "total_debt_limit_amount": total_debt_limit_amount,
        "total_actual_debt_draw": total_actual_debt_draw,
        "principal_repayment_mode": principal_repayment_mode,
        "last_collection_day": last_collection_day,
        "last_payment_day": last_payment_day,
        "bank_rate_pct": bank_rate_pct,
        "inflation_rate_pct": inflation_rate_pct,
    }
