import math
import numpy_financial as npf


EPS = 1e-9


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
        cost_out_pct = float(s["cost_out_pct"])
        name = str(s.get("name", f"Giai đoạn {len(stages) + 1}")).strip() or f"Giai đoạn {len(stages) + 1}"

        if duration_months <= 0:
            raise ValueError(f"{name}: thời lượng giai đoạn phải lớn hơn 0.")
        if payment_pct <= 0:
            raise ValueError(f"{name}: tỷ lệ thanh toán phải lớn hơn 0.")
        if cost_out_pct <= 0:
            raise ValueError(f"{name}: tỷ lệ chi tiền đầu giai đoạn phải lớn hơn 0.")

        stages.append(
            {
                "stage_no": len(stages) + 1,
                "name": name,
                "duration_months": duration_months,
                "payment_pct": payment_pct,
                "cost_out_pct": cost_out_pct,
            }
        )

    if not stages:
        raise ValueError("Phải có ít nhất 1 giai đoạn nghiệm thu.")

    if len(stages) > 5:
        raise ValueError("Tối đa 5 giai đoạn nghiệm thu.")

    total_payment_pct = sum(s["payment_pct"] for s in stages)
    if abs(total_payment_pct - 100.0) > 1e-6:
        raise ValueError("Tổng tỷ lệ thanh toán các giai đoạn phải bằng đúng 100% giá trị hợp đồng.")

    total_cost_out_pct = sum(s["cost_out_pct"] for s in stages)
    if abs(total_cost_out_pct - 100.0) > 1e-6:
        raise ValueError("Tổng tỷ lệ chi tiền đầu các giai đoạn phải bằng đúng 100% giá vốn.")

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
        stage_cost = total_cost * (s["cost_out_pct"] / 100.0)

        stage_plan.append(
            {
                "stage_no": s["stage_no"],
                "name": s["name"],
                "duration_months": s["duration_months"],
                "start_month": start_month,
                "end_month": end_month,
                "collection_month": collection_month,
                "payment_pct": s["payment_pct"],
                "cost_out_pct": s["cost_out_pct"],
                "gross_billing_value": gross_billing_value,
                "stage_cost": stage_cost,
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
    customer_advance = [0.0] * (horizon + 1)
    billing = [0.0] * (horizon + 1)
    net_billing = [0.0] * (horizon + 1)
    collections = [0.0] * (horizon + 1)

    cost = [0.0] * (horizon + 1)
    after_sales = [0.0] * (horizon + 1)
    debt_draw = [0.0] * (horizon + 1)
    interest = [0.0] * (horizon + 1)
    principal = [0.0] * (horizon + 1)
    tax = [0.0] * (horizon + 1)
    project_tax = [0.0] * (horizon + 1)
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
    remaining_advance_to_offset = owner_advance_amount

    for stage in stage_plan:
        gross = stage["gross_billing_value"]
        billing[stage["end_month"]] += gross

        offset_advance = min(gross, remaining_advance_to_offset)
        net_collection = gross - offset_advance
        remaining_advance_to_offset -= offset_advance

        net_billing[stage["end_month"]] += net_collection
        collections[stage["collection_month"]] += net_collection

        stage["advance_offset"] = offset_advance
        stage["net_collection_value"] = net_collection

    # =========================
    # 9. PHÂN BỔ GIÁ VỐN THEO % CHI TIỀN ĐẦU GIAI ĐOẠN
    #    - Mỗi giai đoạn chi tiền ngay ở tháng đầu giai đoạn
    # =========================
    for stage in stage_plan:
        start_month = stage["start_month"]
        cost[start_month] += stage["stage_cost"]

    allocated_cost = sum(cost)
    residual_cost = total_cost - allocated_cost
    if abs(residual_cost) > EPS:
        cost[stage_plan[-1]["start_month"]] += residual_cost
        stage_plan[-1]["stage_cost"] += residual_cost

    # =========================
    # 10. LỊCH GIẢI NGÂN VAY
    #     - tối đa 4 đợt
    #     - % theo GIÁ VỐN
    #     - giải ngân ở đầu kỳ giai đoạn đó
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

    total_debt_draw_amount = sum(debt_draw_amount_by_stage.values())
    if total_debt_draw_amount - total_cost > EPS:
        raise ValueError("Tổng giải ngân vay không được lớn hơn tổng giá vốn.")

    for stage in stage_plan:
        stage_no = stage["stage_no"]
        if stage_no <= 4:
            debt_draw[stage["start_month"]] += debt_draw_amount_by_stage.get(stage_no, 0.0)

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
    # 13. WATERFALL TIỀN MẶT
    # =========================
    def run_waterfall(total_tax_at_horizon):
        interest_local = [0.0] * (horizon + 1)
        principal_local = [0.0] * (horizon + 1)
        tax_local = [0.0] * (horizon + 1)
        tax_local[horizon] = total_tax_at_horizon

        equity_in_local = [0.0] * (horizon + 1)
        equity_out_local = [0.0] * (horizon + 1)

        opening_cash_local = [0.0] * (horizon + 1)
        closing_cash_local = [0.0] * (horizon + 1)
        debt_balance_series_local = [0.0] * (horizon + 1)

        cash_balance = 0.0
        debt_balance = 0.0
        peak_debt_local = 0.0

        for t in timeline:
            opening_cash_local[t] = cash_balance

            # Draw vay ở đầu tháng
            if debt_draw[t] > 0:
                debt_balance += debt_draw[t]

            peak_debt_local = max(peak_debt_local, debt_balance)

            # Lãi tính trên dư nợ sau draw đầu tháng
            interest_due = debt_balance * monthly_interest_rate if debt_balance > EPS else 0.0
            interest_local[t] = interest_due

            inflow = customer_advance[t] + debt_draw[t] + collections[t] + salvage[t]
            outflow_before_principal = cost[t] + after_sales[t] + interest_due + tax_local[t]

            cash_after_ops = cash_balance + inflow - outflow_before_principal

            # Nếu còn tiền thì ưu tiên trả gốc
            if cash_after_ops > EPS and debt_balance > EPS:
                repay = min(cash_after_ops, debt_balance)
                principal_local[t] = repay
                cash_after_ops -= repay
                debt_balance -= repay

            # Nếu âm tiền -> bơm vốn chủ
            if cash_after_ops < -EPS:
                equity_in_local[t] += -cash_after_ops
                cash_after_ops = 0.0

            # Cuối horizon: tất toán hết nợ còn lại bằng vốn chủ nếu cần
            if t == horizon and debt_balance > EPS:
                equity_in_local[t] += debt_balance
                principal_local[t] += debt_balance
                debt_balance = 0.0

            # Cuối horizon: tiền dư mới trả về vốn chủ
            if t == horizon and cash_after_ops > EPS:
                equity_out_local[t] = cash_after_ops
                cash_after_ops = 0.0

            debt_balance_series_local[t] = debt_balance
            closing_cash_local[t] = cash_after_ops
            cash_balance = cash_after_ops

        total_interest_local = sum(interest_local)

        return {
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
        }

    # Pass 1 để xác định tổng lãi vay dùng cho tax thực tế
    pass1 = run_waterfall(total_tax_at_horizon=0.0)
    total_interest_pass1 = pass1["total_interest"]

    # =========================
    # 14. THUẾ
    #     - Equity tax: cho phép tax shield từ lãi vay
    #     - Project tax: không dùng lãi vay để tính project IRR
    # =========================
    pre_tax_profit_equity = deal_value + salvage_value_total - total_cost - after_sales_total - total_interest_pass1
    total_cit = max(0.0, pre_tax_profit_equity) * cit_rate

    pre_tax_profit_project = deal_value + salvage_value_total - total_cost - after_sales_total
    project_tax_total = max(0.0, pre_tax_profit_project) * cit_rate

    # Pass 2 có tax thực tế
    pass2 = run_waterfall(total_tax_at_horizon=total_cit)

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

    project_tax[horizon] = project_tax_total

    # =========================
    # 15. AR, PROJECT CF, EQUITY CF
    # =========================
    running_ar = 0.0
    project_cf = [0.0] * (horizon + 1)
    equity_cf = [0.0] * (horizon + 1)

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

    # =========================
    # 16. CHỈ SỐ
    # =========================
    project_irr_month = safe_irr(project_cf)
    equity_irr_month = safe_irr(equity_cf)

    project_irr_annual = annualize_monthly_irr(project_irr_month)
    equity_irr_annual = annualize_monthly_irr(equity_irr_month)

    cum_equity_cf = []
    running_cum_equity_cf = 0.0
    for x in equity_cf:
        running_cum_equity_cf += x
        cum_equity_cf.append(running_cum_equity_cf)

    total_equity_in = sum(equity_in)
    total_equity_out = sum(equity_out)

    running_equity_at_risk = 0.0
    peak_equity_at_risk = 0.0
    payback_month = None
    has_called_equity = False

    for t in timeline:
        if equity_in[t] > EPS:
            has_called_equity = True

        running_equity_at_risk += equity_in[t] - equity_out[t]
        peak_equity_at_risk = max(peak_equity_at_risk, running_equity_at_risk)

        if has_called_equity and running_equity_at_risk <= EPS and payback_month is None:
            payback_month = t

    if total_equity_in <= EPS:
        payback_month = 0
        payback_message = "Mô hình không cần bơm vốn chủ, nên thời gian hoàn vốn được xem là 0 tháng."
    elif payback_month is None:
        payback_message = "Chưa hoàn vốn trong toàn bộ timeline của mô hình."
    else:
        payback_message = f"Hoàn vốn sau {payback_month} tháng."

    equity_multiple = None
    if total_equity_in > EPS:
        equity_multiple = total_equity_out / total_equity_in

    # Trong mô hình hiện tại, MOIC cùng cơ sở với Equity Multiple
    moic = equity_multiple

    net_profit = deal_value + salvage_value_total - total_cost - after_sales_total - total_interest - total_cit
    net_profit_margin = None
    if deal_value > EPS:
        net_profit_margin = (net_profit / deal_value) * 100.0

    decision = get_decision(equity_irr_annual)
    decision_basis = (
        "Đánh giá sơ bộ hiện đang dựa trên IRR vốn chủ năm hóa: "
        "GO nếu IRR >= 25%, REVIEW nếu IRR từ 15% đến dưới 25%, "
        "NO GO nếu IRR < 15%. Nếu IRR không tính được thì mặc định REVIEW."
    )

    return {
        "timeline": timeline,
        "stage_plan": stage_plan,

        "customer_advance": customer_advance,
        "billing": billing,
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

        "project_cf": project_cf,
        "project_irr_annual": project_irr_annual,
        "equity_irr_annual": equity_irr_annual,

        "equity_multiple": equity_multiple,
        "moic": moic,
        "net_profit": net_profit,
        "net_profit_margin": net_profit_margin,
        "payback_month": payback_month,
        "payback_message": payback_message,

        "peak_debt": peak_debt,
        "peak_equity_at_risk": peak_equity_at_risk,
        "decision": decision,
        "decision_basis": decision_basis,

        "deal_value": deal_value,
        "total_cost": total_cost,
        "owner_advance_amount": owner_advance_amount,
        "after_sales_total": after_sales_total,
        "salvage_value_total": salvage_value_total,
        "total_interest": total_interest,
        "total_cit": total_cit,
        "project_tax_total": project_tax_total,
        "total_equity_in": total_equity_in,
        "total_equity_out": total_equity_out,
        "total_debt_draw_amount": total_debt_draw_amount,
    }
