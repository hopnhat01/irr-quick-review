import math
import numpy_financial as npf


def safe_irr(cashflows):
    if not cashflows or len(cashflows) < 2:
        return None

    vals = [float(x) for x in cashflows]
    has_positive = any(v > 0 for v in vals)
    has_negative = any(v < 0 for v in vals)

    if not (has_positive and has_negative):
        return None

    try:
        irr = npf.irr(vals)
        if irr is None or math.isnan(irr) or irr <= -1:
            return None
        return float(irr)
    except Exception:
        return None


def annualize_monthly_irr(monthly_irr):
    if monthly_irr is None:
        return None
    return ((1 + monthly_irr) ** 12 - 1) * 100


def get_decision(irr_annual_pct):
    if irr_annual_pct is None:
        return "REVIEW"
    if irr_annual_pct >= 25:
        return "GO"
    if irr_annual_pct >= 15:
        return "REVIEW"
    return "NO GO"


def build_model(inputs):
    # =========================
    # 1. INPUT
    # =========================
    deal_value = float(inputs["deal_value"])
    cost_pct = float(inputs["cost_pct"]) / 100.0
    salvage_pct = float(inputs.get("salvage_pct", 0.0)) / 100.0
    cit_rate = float(inputs.get("tax_rate", 0.0)) / 100.0
    avg_dso_days = int(inputs.get("avg_dso_days", 0))

    # ĐÃ ĐỔI: % theo GIÁ TRỊ HỢP ĐỒNG
    owner_advance_pct = float(inputs.get("owner_advance_pct", 0.0)) / 100.0

    interest_rate_annual = float(inputs.get("interest_rate", 0.0)) / 100.0
    after_sales_pct = float(inputs.get("after_sales_pct", 0.0)) / 100.0
    warranty_months = int(inputs.get("warranty_months", 0))

    raw_stages = inputs.get("stages", [])
    raw_debt_draw_schedule = inputs.get("debt_draw_schedule", [])

    # =========================
    # 2. VALIDATION
    # =========================
    if deal_value <= 0:
        raise ValueError("Giá trị hợp đồng phải lớn hơn 0.")

    if not (0 <= cost_pct <= 1):
        raise ValueError("Tỷ lệ giá vốn phải nằm trong khoảng 0% đến 100%.")

    if not (0 <= salvage_pct <= 1):
        raise ValueError("Giá trị thu hồi cuối kỳ phải nằm trong khoảng 0% đến 100%.")

    if not (0 <= cit_rate <= 1):
        raise ValueError("Thuế CIT phải nằm trong khoảng 0% đến 100%.")

    if not (0 <= owner_advance_pct <= 1):
        raise ValueError("Tỷ lệ tạm ứng CĐT phải nằm trong khoảng 0% đến 100% giá trị hợp đồng.")

    if not (0 <= after_sales_pct <= 1):
        raise ValueError("Tỷ lệ bảo hành / bảo hiểm hậu mãi phải nằm trong khoảng 0% đến 100% giá trị hợp đồng.")

    if warranty_months < 0:
        raise ValueError("Thời hạn bảo hành không được âm.")

    # =========================
    # 3. CHUẨN HÓA STAGES
    # =========================
    stages = []
    for s in raw_stages:
        duration_months = int(s["duration_months"])
        payment_pct = float(s["payment_pct"])
        name = str(s.get("name", f"Giai đoạn {len(stages) + 1}")).strip() or f"Giai đoạn {len(stages) + 1}"

        if duration_months <= 0:
            raise ValueError(f"{name}: thời lượng giai đoạn phải lớn hơn 0.")
        if payment_pct <= 0:
            raise ValueError(f"{name}: tỷ lệ thanh toán phải lớn hơn 0.")

        stages.append(
            {
                "stage_no": len(stages) + 1,
                "name": name,
                "duration_months": duration_months,
                "payment_pct": payment_pct,
            }
        )

    if not stages:
        raise ValueError("Phải có ít nhất 1 giai đoạn nghiệm thu.")

    if len(stages) > 5:
        raise ValueError("Tối đa 5 giai đoạn nghiệm thu.")

    total_payment_pct = sum(s["payment_pct"] for s in stages)
    if abs(total_payment_pct - 100.0) > 1e-6:
        raise ValueError("Tổng tỷ lệ thanh toán các giai đoạn phải bằng đúng 100% giá trị hợp đồng.")

    # =========================
    # 4. THÔNG SỐ CƠ SỞ
    # =========================
    total_cost = deal_value * cost_pct
    salvage_value_total = deal_value * salvage_pct
    owner_advance_amount = deal_value * owner_advance_pct
    after_sales_total = deal_value * after_sales_pct

    monthly_interest_rate = interest_rate_annual / 12.0
    delay_month = math.ceil(avg_dso_days / 30.0)

    # =========================
    # 5. TIMELINE THEO GIAI ĐOẠN
    # =========================
    stage_plan = []
    month_cursor = 1

    for s in stages:
        start_month = month_cursor
        end_month = start_month + s["duration_months"] - 1
        collection_month = end_month + delay_month
        gross_billing_value = deal_value * (s["payment_pct"] / 100.0)

        stage_plan.append(
            {
                "stage_no": s["stage_no"],
                "name": s["name"],
                "duration_months": s["duration_months"],
                "start_month": start_month,
                "end_month": end_month,
                "collection_month": collection_month,
                "payment_pct": s["payment_pct"],
                "gross_billing_value": gross_billing_value,
            }
        )

        month_cursor = end_month + 1

    last_stage_end = stage_plan[-1]["end_month"]
    last_collection_month = max(x["collection_month"] for x in stage_plan)
    after_sales_start_month = last_stage_end + 1
    after_sales_end_month = last_stage_end + max(warranty_months, 0)
    horizon = max(last_collection_month, after_sales_end_month)

    timeline = list(range(horizon + 1))

    # =========================
    # 6. KHỞI TẠO MẢNG
    # =========================
    customer_advance = [0.0] * (horizon + 1)   # tiền tạm ứng CĐT
    billing = [0.0] * (horizon + 1)            # nghiệm thu gross
    collections = [0.0] * (horizon + 1)        # thu tiền net
    cost = [0.0] * (horizon + 1)               # chi đầu kỳ
    after_sales = [0.0] * (horizon + 1)
    debt_draw = [0.0] * (horizon + 1)
    interest = [0.0] * (horizon + 1)
    principal = [0.0] * (horizon + 1)
    tax = [0.0] * (horizon + 1)
    salvage = [0.0] * (horizon + 1)

    equity_in = [0.0] * (horizon + 1)
    equity_out = [0.0] * (horizon + 1)

    opening_cash = [0.0] * (horizon + 1)
    closing_cash = [0.0] * (horizon + 1)
    debt_balance_series = [0.0] * (horizon + 1)
    ar_balance = [0.0] * (horizon + 1)

    # =========================
    # 7. TẠM ỨNG CĐT TẠI T0
    # =========================
    customer_advance[0] = owner_advance_amount

    # =========================
    # 8. BILLING VÀ COLLECTION
    #    - khách thanh toán theo giá trị hợp đồng
    #    - tạm ứng CĐT được trừ dần khỏi các đợt thu sau
    # =========================
    for stage in stage_plan:
        billing[stage["end_month"]] += stage["gross_billing_value"]

    remaining_advance_to_offset = owner_advance_amount

    for stage in stage_plan:
        gross = stage["gross_billing_value"]
        offset_advance = min(gross, remaining_advance_to_offset)
        net_collection = gross - offset_advance
        remaining_advance_to_offset -= offset_advance

        collections[stage["collection_month"]] += net_collection

        stage["advance_offset"] = offset_advance
        stage["net_collection_value"] = net_collection

    # =========================
    # 9. LỊCH GIẢI NGÂN VAY
    #    - tối đa 4 đợt
    #    - % theo GIÁ VỐN
    #    - giải ngân ở đầu kỳ giai đoạn đó
    # =========================
    debt_draw_amount_by_stage = {i: 0.0 for i in range(1, 6)}

    for item in raw_debt_draw_schedule:
        stage_no = int(item["stage_no"])
        draw_pct_cost = float(item["draw_pct_cost"])

        if draw_pct_cost < 0:
            raise ValueError(f"Giải ngân vay giai đoạn {stage_no} không được âm.")
        if stage_no < 1 or stage_no > 4:
            raise ValueError("Giải ngân vay chỉ được phép từ giai đoạn 1 đến giai đoạn 4.")
        if stage_no > len(stage_plan):
            continue

        draw_amount = total_cost * (draw_pct_cost / 100.0)
        debt_draw_amount_by_stage[stage_no] += draw_amount

    for stage in stage_plan:
        stage_no = stage["stage_no"]
        if stage_no <= 4:
            debt_draw[stage["start_month"]] += debt_draw_amount_by_stage.get(stage_no, 0.0)

    total_debt_draw_amount = sum(debt_draw_amount_by_stage.values())

    # =========================
    # 10. CHI PHÍ THEO LOGIC MỚI
    #     - Giai đoạn 0: dùng tạm ứng CĐT
    #     - Giai đoạn 1..4: chi đầu kỳ theo khoản vay của giai đoạn đó
    #     - Nếu chưa đủ tổng giá vốn: phần còn thiếu dồn vào đầu giai đoạn cuối
    # =========================
    remaining_cost = total_cost

    # stage 0 cost ở T0
    stage0_cost = min(owner_advance_amount, remaining_cost)
    cost[0] += stage0_cost
    remaining_cost -= stage0_cost

    stage_cost_amount = {i: 0.0 for i in range(1, len(stage_plan) + 1)}

    for stage in stage_plan:
        stage_no = stage["stage_no"]
        if stage_no <= 4:
            alloc = min(debt_draw_amount_by_stage.get(stage_no, 0.0), remaining_cost)
            stage_cost_amount[stage_no] += alloc
            remaining_cost -= alloc

    if remaining_cost > 1e-9:
        last_stage_no = stage_plan[-1]["stage_no"]
        stage_cost_amount[last_stage_no] += remaining_cost
        remaining_cost = 0.0

    # kiểm tra funding không vượt chi phí quá nhiều
    if owner_advance_amount + total_debt_draw_amount > total_cost + 1e-9:
        raise ValueError(
            "Tạm ứng CĐT cộng với tổng giải ngân vay đang lớn hơn tổng giá vốn. "
            "Hãy giảm tạm ứng hoặc giảm tỷ lệ giải ngân vay."
        )

    for stage in stage_plan:
        stage_no = stage["stage_no"]
        c = stage_cost_amount.get(stage_no, 0.0)
        cost[stage["start_month"]] += c
        stage["stage_cost"] = c

    # =========================
    # 11. HẬU MÃI / BẢO HÀNH / BẢO HIỂM
    # =========================
    if after_sales_total > 0 and warranty_months > 0:
        monthly_after_sales = after_sales_total / warranty_months
        for t in range(after_sales_start_month, after_sales_end_month + 1):
            after_sales[t] += monthly_after_sales

    # =========================
    # 12. THU HỒI CUỐI KỲ
    # =========================
    salvage[horizon] += salvage_value_total

    # =========================
    # 13. PASS 1: TÍNH LÃI VÀ GỐC
    #     - draw ở đầu tháng
    #     - lãi hàng tháng trên dư nợ sau draw
    #     - gốc trả một lần ở kỳ thu cuối cùng
    # =========================
    debt_balance = 0.0
    peak_debt = 0.0

    for t in timeline:
        if debt_draw[t] > 0:
            debt_balance += debt_draw[t]

        peak_debt = max(peak_debt, debt_balance)

        interest[t] = debt_balance * monthly_interest_rate if debt_balance > 0 else 0.0

        if t == last_collection_month and debt_balance > 0:
            principal[t] = debt_balance
            debt_balance = 0.0

    # =========================
    # 14. THUẾ CIT
    #     - đơn giản hóa: nộp cuối horizon
    #     - cho phép tax shield từ lãi vay
    # =========================
    total_interest = sum(interest)
    taxable_profit = deal_value + salvage_value_total - total_cost - after_sales_total - total_interest
    total_cit = max(0.0, taxable_profit) * cit_rate
    tax[horizon] += total_cit

    # =========================
    # 15. PASS 2: WATERFALL TIỀN MẶT
    #     - giữ tiền trong dự án
    #     - thiếu thì equity bơm
    #     - cuối cùng còn dư mới trả về equity
    # =========================
    cash_balance = 0.0
    debt_balance = 0.0
    peak_debt_actual = 0.0

    project_cf = [0.0] * (horizon + 1)
    equity_cf = [0.0] * (horizon + 1)

    running_ar = 0.0

    for t in timeline:
        opening_cash[t] = cash_balance

        if debt_draw[t] > 0:
            debt_balance += debt_draw[t]

        peak_debt_actual = max(peak_debt_actual, debt_balance)

        inflow = customer_advance[t] + debt_draw[t] + collections[t] + salvage[t]
        outflow = cost[t] + after_sales[t] + interest[t] + principal[t] + tax[t]

        cash_after = cash_balance + inflow - outflow

        if cash_after < 0:
            equity_in[t] = -cash_after
            cash_after = 0.0

        if t == horizon and cash_after > 0:
            equity_out[t] = cash_after
            cash_after = 0.0

        if principal[t] > 0:
            debt_balance -= principal[t]
            if debt_balance < 0:
                debt_balance = 0.0

        debt_balance_series[t] = debt_balance
        closing_cash[t] = cash_after
        cash_balance = cash_after

        # AR balance
        running_ar += billing[t] - collections[t]
        ar_balance[t] = running_ar

        # Project CF: không có debt/equity
        project_cf[t] = customer_advance[t] + collections[t] + salvage[t] - cost[t] - after_sales[t] - tax[t]

        # Equity CF: chỉ nhìn tiền equity thực bơm / rút
        equity_cf[t] = -equity_in[t] + equity_out[t]

    # =========================
    # 16. CHỈ SỐ
    # =========================
    project_irr_month = safe_irr(project_cf)
    equity_irr_month = safe_irr(equity_cf)

    project_irr_annual = annualize_monthly_irr(project_irr_month)
    equity_irr_annual = annualize_monthly_irr(equity_irr_month)

    cum_equity_cf = []
    running = 0.0
    for x in equity_cf:
        running += x
        cum_equity_cf.append(running)

    payback_month = None
    for i, v in enumerate(cum_equity_cf):
        if v >= 0:
            payback_month = i
            break

    running_equity_at_risk = 0.0
    peak_equity_at_risk = 0.0
    total_equity_in = 0.0
    total_equity_out = 0.0

    for t in timeline:
        total_equity_in += equity_in[t]
        total_equity_out += equity_out[t]
        running_equity_at_risk += equity_in[t] - equity_out[t]
        peak_equity_at_risk = max(peak_equity_at_risk, running_equity_at_risk)

    equity_multiple = None
    if total_equity_in > 0:
        equity_multiple = total_equity_out / total_equity_in

    decision = get_decision(equity_irr_annual)

    # stage plan enrich
    for stage in stage_plan:
        stage["advance_offset"] = stage.get("advance_offset", 0.0)
        stage["net_collection_value"] = stage.get("net_collection_value", 0.0)
        stage["stage_cost"] = stage.get("stage_cost", 0.0)

    return {
        "timeline": timeline,
        "stage_plan": stage_plan,

        "customer_advance": customer_advance,
        "billing": billing,
        "collections": collections,
        "ar_balance": ar_balance,

        "cost": cost,
        "after_sales": after_sales,
        "interest": interest,
        "principal": principal,
        "tax": tax,
        "salvage": salvage,

        "debt_draw": debt_draw,
        "debt_balance": debt_balance_series,

        "equity_in": equity_in,
        "equity_out": equity_out,
        "equity_cf": equity_cf,
        "cum_equity_cf": cum_equity_cf,

        "opening_cash": opening_cash,
        "closing_cash": closing_cash,

        "project_cf": project_cf,
        "project_irr_annual": project_irr_annual,
        "equity_irr_annual": equity_irr_annual,
        "equity_multiple": equity_multiple,
        "payback_month": payback_month,
        "peak_debt": peak_debt_actual,
        "peak_equity_at_risk": peak_equity_at_risk,
        "decision": decision,

        "deal_value": deal_value,
        "total_cost": total_cost,
        "owner_advance_amount": owner_advance_amount,
        "after_sales_total": after_sales_total,
        "salvage_value_total": salvage_value_total,
        "total_interest": total_interest,
        "total_cit": total_cit,
        "stage0_cost": stage0_cost,
    }
