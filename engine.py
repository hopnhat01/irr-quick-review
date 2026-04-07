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
    # 1. ĐỌC INPUT
    # =========================
    deal_value = float(inputs["deal_value"])
    cost_pct = float(inputs["cost_pct"]) / 100.0
    salvage_pct = float(inputs.get("salvage_pct", 0.0)) / 100.0
    cit_rate = float(inputs.get("tax_rate", 0.0)) / 100.0  # CIT
    avg_dso_days = int(inputs.get("avg_dso_days", 0))

    owner_advance_pct = float(inputs.get("owner_advance_pct", 0.0)) / 100.0  # % theo giá vốn
    interest_rate_annual = float(inputs.get("interest_rate", 0.0)) / 100.0

    after_sales_pct = float(inputs.get("after_sales_pct", 0.0)) / 100.0  # % theo giá trị hợp đồng
    warranty_months = int(inputs.get("warranty_months", 0))

    raw_stages = inputs.get("stages", [])
    raw_debt_draw_schedule = inputs.get("debt_draw_schedule", [])

    if deal_value <= 0:
        raise ValueError("Giá trị hợp đồng phải lớn hơn 0.")

    if cost_pct < 0 or cost_pct > 1:
        raise ValueError("Tỷ lệ giá vốn phải nằm trong khoảng 0% đến 100%.")

    if salvage_pct < 0 or salvage_pct > 1:
        raise ValueError("Giá trị thu hồi cuối kỳ phải nằm trong khoảng 0% đến 100%.")

    if cit_rate < 0 or cit_rate > 1:
        raise ValueError("Thuế CIT phải nằm trong khoảng 0% đến 100%.")

    if owner_advance_pct < 0 or owner_advance_pct > 1:
        raise ValueError("Tỷ lệ tạm ứng CĐT phải nằm trong khoảng 0% đến 100% giá vốn.")

    if after_sales_pct < 0 or after_sales_pct > 1:
        raise ValueError("Tỷ lệ bảo hành / bảo hiểm hậu mãi phải nằm trong khoảng 0% đến 100% giá trị hợp đồng.")

    if warranty_months < 0:
        raise ValueError("Thời hạn bảo hành không được âm.")

    # =========================
    # 2. CHUẨN HÓA STAGES
    # =========================
    stages = []
    for s in raw_stages:
        duration_months = int(s["duration_months"])
        payment_pct = float(s["payment_pct"])
        name = str(s.get("name", f"Giai đoạn {len(stages) + 1}")).strip() or f"Giai đoạn {len(stages) + 1}"

        if duration_months <= 0:
            raise ValueError(f"{name}: thời lượng giai đoạn phải > 0.")
        if payment_pct <= 0:
            raise ValueError(f"{name}: tỷ lệ thanh toán phải > 0.")

        stages.append(
            {
                "stage_no": len(stages) + 1,
                "name": name,
                "duration_months": duration_months,
                "payment_pct": payment_pct,
            }
        )

    if not stages:
        raise ValueError("Phải có ít nhất 1 giai đoạn.")

    if len(stages) > 5:
        raise ValueError("Tối đa 5 giai đoạn.")

    total_payment_pct = sum(s["payment_pct"] for s in stages)
    if abs(total_payment_pct - 100.0) > 1e-6:
        raise ValueError("Tổng tỷ lệ thanh toán các giai đoạn phải bằng đúng 100% giá trị hợp đồng.")

    # =========================
    # 3. THÔNG SỐ CƠ SỞ
    # =========================
    total_cost = deal_value * cost_pct
    salvage_value_total = deal_value * salvage_pct
    owner_advance_amount = total_cost * owner_advance_pct
    after_sales_total = deal_value * after_sales_pct

    monthly_interest_rate = interest_rate_annual / 12.0
    delay_month = math.ceil(avg_dso_days / 30.0)

    # =========================
    # 4. TIMELINE CÁC GIAI ĐOẠN
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
    # 5. KHỞI TẠO MẢNG
    # =========================
    customer_advance = [0.0] * (horizon + 1)   # tiền tạm ứng từ CĐT tại T0
    billing = [0.0] * (horizon + 1)            # nghiệm thu / hóa đơn gross
    collections = [0.0] * (horizon + 1)        # tiền thu NET sau khi trừ phần đã tạm ứng
    cost = [0.0] * (horizon + 1)               # chi phí đầu giai đoạn
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

    # =========================
    # 6. TẠM ỨNG CĐT TẠI T0
    # =========================
    customer_advance[0] = owner_advance_amount

    # =========================
    # 7. BILLING VÀ COLLECTIONS
    #    - Billing gross theo payment_pct của từng stage
    #    - Collections net sau khi trừ dần khoản tạm ứng CĐT
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
    # 8. VAY THEO GIAI ĐOẠN
    #    Logic khớp input app hiện tại:
    #    - T0: có tạm ứng CĐT
    #    - Stage 1 bắt đầu vay GĐ1
    #    - Chi phí đầu stage 1 = tạm ứng + vay GĐ1
    #    - Chi phí đầu stage 2 = vay GĐ2
    #    - Chi phí đầu stage 3 = vay GĐ3
    #    - Chi phí đầu stage 4 = vay GĐ4
    #    - Nếu tổng này chưa đủ 100% giá vốn => phần còn thiếu dồn vào đầu stage cuối
    # =========================
    debt_draw_amount_by_stage = {i: 0.0 for i in range(1, 6)}

    for item in raw_debt_draw_schedule:
        stage_no = int(item["stage_no"])
        draw_pct_cost = float(item["draw_pct_cost"])

        if draw_pct_cost < 0:
            raise ValueError(f"Giải ngân vay giai đoạn {stage_no} không được âm.")

        if stage_no < 1 or stage_no > 4:
            raise ValueError("Giải ngân vay chỉ được phép từ giai đoạn 1 đến giai đoạn 4 theo input hiện tại.")

        if stage_no > len(stage_plan):
            continue

        amt = total_cost * (draw_pct_cost / 100.0)
        debt_draw_amount_by_stage[stage_no] += amt

    # Ghi lịch giải ngân vay vào timeline
    for stage in stage_plan:
        stage_no = stage["stage_no"]
        start_month = stage["start_month"]

        if stage_no <= 4:
            debt_draw[start_month] += debt_draw_amount_by_stage.get(stage_no, 0.0)

    # =========================
    # 9. CHI PHÍ ĐẦU GIAI ĐOẠN
    #    - Stage 1: owner advance + debt GĐ1
    #    - Stage 2: debt GĐ2
    #    - Stage 3: debt GĐ3
    #    - Stage 4: debt GĐ4
    #    - Stage 5: phần còn lại (nếu có)
    # =========================
    stage_cost_amount = {i: 0.0 for i in range(1, len(stage_plan) + 1)}

    if len(stage_plan) >= 1:
        stage_cost_amount[1] += owner_advance_amount
        stage_cost_amount[1] += debt_draw_amount_by_stage.get(1, 0.0)

    if len(stage_plan) >= 2:
        stage_cost_amount[2] += debt_draw_amount_by_stage.get(2, 0.0)

    if len(stage_plan) >= 3:
        stage_cost_amount[3] += debt_draw_amount_by_stage.get(3, 0.0)

    if len(stage_plan) >= 4:
        stage_cost_amount[4] += debt_draw_amount_by_stage.get(4, 0.0)

    planned_cost_allocated = sum(stage_cost_amount.values())
    residual_cost = total_cost - planned_cost_allocated

    # Nếu lịch funding chưa đủ 100% giá vốn, dồn phần còn lại vào đầu giai đoạn cuối
    if residual_cost > 1e-9:
        last_stage_no = stage_plan[-1]["stage_no"]
        stage_cost_amount[last_stage_no] += residual_cost
    elif residual_cost < -1e-9:
        raise ValueError("Tạm ứng CĐT + tổng giải ngân vay đang vượt tổng giá vốn. Kiểm tra lại input.")

    for stage in stage_plan:
        stage_no = stage["stage_no"]
        start_month = stage["start_month"]
        c = stage_cost_amount.get(stage_no, 0.0)
        cost[start_month] += c
        stage["stage_cost"] = c

    # =========================
    # 10. BẢO HÀNH / BẢO HIỂM HẬU MÃI
    # =========================
    if after_sales_total > 0 and warranty_months > 0:
        monthly_after_sales = after_sales_total / warranty_months
        for t in range(after_sales_start_month, after_sales_end_month + 1):
            after_sales[t] += monthly_after_sales

    # =========================
    # 11. THU HỒI CUỐI KỲ
    # =========================
    salvage[horizon] += salvage_value_total

    # =========================
    # 12. PASS 1: TÍNH DƯ NỢ, LÃI, GỐC
    #     - Draw ở đầu tháng
    #     - Lãi tính trên dư nợ sau khi draw tháng đó
    #     - Gốc trả 1 lần ở kỳ collection cuối cùng
    # =========================
    debt_balance = 0.0
    peak_debt = 0.0

    for t in timeline:
        if debt_draw[t] > 0:
            debt_balance += debt_draw[t]

        peak_debt = max(peak_debt, debt_balance)

        # Trả lãi định kỳ hàng tháng
        interest[t] = debt_balance * monthly_interest_rate if debt_balance > 0 else 0.0

        # Trả gốc cuối cùng khi tới kỳ thu tiền cuối của dự án
        if t == last_collection_month and debt_balance > 0:
            principal[t] = debt_balance
            debt_balance = 0.0

        debt_balance_series[t] = debt_balance

    # =========================
    # 13. THUẾ CIT
    #     Đơn giản hóa: thanh toán cuối horizon
    # =========================
    total_interest = sum(interest)
    taxable_profit = deal_value + salvage_value_total - total_cost - after_sales_total - total_interest
    total_cit = max(0.0, taxable_profit) * cit_rate
    tax[horizon] += total_cit

    # =========================
    # 14. PASS 2: WATERFALL CASH THỰC TẾ
    #     - Giữ cash lại trong dự án
    #     - Chỉ nếu âm thì equity bơm thêm
    #     - Chỉ trả equity_out ở tháng cuối nếu còn tiền dư
    # =========================
    cash_balance = 0.0
    debt_balance = 0.0
    peak_debt_actual = 0.0

    project_cf = [0.0] * (horizon + 1)
    equity_cf = [0.0] * (horizon + 1)

    for t in timeline:
        opening_cash[t] = cash_balance

        if debt_draw[t] > 0:
            debt_balance += debt_draw[t]

        peak_debt_actual = max(peak_debt_actual, debt_balance)

        inflow = customer_advance[t] + debt_draw[t] + collections[t] + salvage[t]
        outflow = cost[t] + after_sales[t] + interest[t] + principal[t] + tax[t]

        cash_after = cash_balance + inflow - outflow

        # Nếu âm -> vốn chủ bơm vào để bù thiếu hụt
        if cash_after < 0:
            equity_in[t] = -cash_after
            cash_after = 0.0

        # Theo logic mới: không trả về equity mỗi tháng,
        # mà giữ lại trong dự án để nuôi các stage tiếp theo
        if t == horizon and cash_after > 0:
            equity_out[t] = cash_after
            cash_after = 0.0

        # Cập nhật debt balance theo principal
        if principal[t] > 0:
            debt_balance -= principal[t]
            if debt_balance < 0:
                debt_balance = 0.0

        debt_balance_series[t] = debt_balance
        closing_cash[t] = cash_after
        cash_balance = cash_after

        # Project cash flow: dòng tiền dự án trước financing
        project_cf[t] = customer_advance[t] + collections[t] + salvage[t] - cost[t] - after_sales[t] - tax[t]

        # Equity cash flow: chỉ nhìn phần vốn chủ bơm / thu hồi
        equity_cf[t] = -equity_in[t] + equity_out[t]

    # =========================
    # 15. CÁC CHỈ SỐ
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
    for t in timeline:
        running_equity_at_risk += equity_in[t]
        running_equity_at_risk -= equity_out[t]
        peak_equity_at_risk = max(peak_equity_at_risk, running_equity_at_risk)

    decision = get_decision(equity_irr_annual)

    # =========================
    # 16. BỔ SUNG THÔNG TIN STAGE PLAN
    # =========================
    for stage in stage_plan:
        stage["gross_billing_value"] = stage.get("gross_billing_value", 0.0)
        stage["advance_offset"] = stage.get("advance_offset", 0.0)
        stage["net_collection_value"] = stage.get("net_collection_value", 0.0)
        stage["stage_cost"] = stage.get("stage_cost", 0.0)

    return {
        "timeline": timeline,
        "stage_plan": stage_plan,

        "customer_advance": customer_advance,
        "billing": billing,
        "collections": collections,

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
    }
