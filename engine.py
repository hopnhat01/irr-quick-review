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


def fisher_real_rate_pct(nominal_annual_pct, inflation_annual_pct):
    if nominal_annual_pct is None or inflation_annual_pct is None:
        return None

    nominal = nominal_annual_pct / 100.0
    inflation = inflation_annual_pct / 100.0

    if (1 + inflation) <= EPS:
        return None

    return (((1 + nominal) / (1 + inflation)) - 1) * 100


def classify_real_irr_vs_bank(real_irr_pct, bank_real_rate_pct):
    if real_irr_pct is None or bank_real_rate_pct is None:
        return (
            "REVIEW",
            None,
            "Không tính được đầy đủ IRR vốn chủ thực hoặc lãi suất ngân hàng thực để so sánh theo Fisher.",
        )

    spread = real_irr_pct - bank_real_rate_pct

    if spread >= 5:
        return (
            "GO",
            spread,
            f"IRR vốn chủ thực cao hơn lãi suất ngân hàng thực {spread:.2f} điểm %, tạo chênh lệch đủ hấp dẫn so với kênh gửi ngân hàng.",
        )

    if spread >= 0:
        return (
            "REVIEW",
            spread,
            f"IRR vốn chủ thực chỉ cao hơn lãi suất ngân hàng thực {spread:.2f} điểm %, chênh lệch dương nhưng chưa đủ dày để an toàn.",
        )

    return (
        "NO GO",
        spread,
        f"IRR vốn chủ thực thấp hơn lãi suất ngân hàng thực {abs(spread):.2f} điểm %, nên hiệu quả thực chưa hấp dẫn bằng benchmark ngân hàng.",
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


def aggregate_decision(real_irr_status, npm_status, multiple_status):
    if real_irr_status == "NO GO":
        return "NO GO"

    if npm_status == "NO GO" and multiple_status == "NO GO":
        return "NO GO"

    if real_irr_status == "GO" and npm_status != "NO GO" and multiple_status != "NO GO":
        return "GO"

    return "REVIEW"


def build_model(inputs):
    # =========================
    # 1. INPUT
    # =========================
    gross_deal_value = float(inputs["deal_value"])
    contract_discount_pct = float(inputs.get("contract_discount_pct", 0.0)) / 100.0
    cost_pct = float(inputs["cost_pct"]) / 100.0
    salvage_pct = float(inputs.get("salvage_pct", 0.0)) / 100.0
    cit_rate = float(inputs.get("tax_rate", 0.0)) / 100.0
    avg_dso_days = int(inputs.get("avg_dso_days", 0))

    owner_advance_pct = float(inputs.get("owner_advance_pct", 0.0)) / 100.0
    interest_rate_annual = float(inputs.get("interest_rate", 0.0)) / 100.0
    bank_rate_pct = float(inputs.get("bank_rate_pct", 0.0))
    inflation_rate_pct = float(inputs.get("inflation_rate_pct", 0.0))
    principal_repayment_mode = str(inputs.get("principal_repayment_mode", "Trả đều theo tháng"))
    after_sales_pct = float(inputs.get("after_sales_pct", 0.0)) / 100.0
    warranty_months = int(inputs.get("warranty_months", 0))

    raw_stages = inputs.get("stages", [])
    raw_debt_draw_schedule = inputs.get("debt_draw_schedule", [])

    # =========================
    # 2. VALIDATION
    # =========================
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

    if warranty_months < 0:
        raise ValueError("Thời hạn bảo hành không được âm.")

    valid_principal_modes = {
        "Trả đều theo tháng",
        "Trả toàn bộ tại tháng thu tiền cuối cùng của giai đoạn nghiệm thu cuối",
    }
    if principal_repayment_mode not in valid_principal_modes:
        raise ValueError("Phương thức trả gốc vay không hợp lệ.")

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
    # 4. THÔNG SỐ CƠ BẢN
    # =========================
    contract_discount_amount = gross_deal_value * contract_discount_pct
    net_contract_value = gross_deal_value - contract_discount_amount

    total_cost = gross_deal_value * cost_pct
    salvage_value_total = gross_deal_value * salvage_pct
    owner_advance_amount = net_contract_value * owner_advance_pct
    after_sales_total = gross_deal_value * after_sales_pct

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

        gross_contract_billing_value = gross_deal_value * (s["payment_pct"] / 100.0)
        stage_discount_amount = contract_discount_amount * (s["payment_pct"] / 100.0)
        net_stage_billing_value = net_contract_value * (s["payment_pct"] / 100.0)
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
                "gross_contract_billing_value": gross_contract_billing_value,
                "stage_discount_amount": stage_discount_amount,
                "net_stage_billing_value": net_stage_billing_value,
                "stage_cost": stage_cost,
                "advance_offset": 0.0,
                "net_collection_value": 0.0,
                "customer_cash_used_for_stage_cost": 0.0,
                "actual_debt_draw": 0.0,
                "actual_equity_for_stage_cost": 0.0,
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
    # 6. KHỞI TẠO CÁC MẢNG CỐ ĐỊNH
    # =========================
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

    # Tạm ứng CĐT tại T0, tính trên giá trị hợp đồng sau chiết khấu
    customer_advance[0] = owner_advance_amount

    # Billing / collection
    remaining_advance_to_offset = owner_advance_amount
    for stage in stage_plan:
        gross_stage_billing = stage["gross_contract_billing_value"]
        stage_discount = stage["stage_discount_amount"]
        net_stage_billing = stage["net_stage_billing_value"]

        billing_gross[stage["end_month"]] += gross_stage_billing
        billing_discount[stage["end_month"]] += stage_discount
        billing_net[stage["end_month"]] += net_stage_billing

        offset_advance = min(net_stage_billing, remaining_advance_to_offset)
        net_collection = net_stage_billing - offset_advance
        remaining_advance_to_offset -= offset_advance

        net_billing[stage["end_month"]] += net_collection
        collections[stage["collection_month"]] += net_collection

        stage["advance_offset"] = offset_advance
        stage["net_collection_value"] = net_collection

    # Chi đầu giai đoạn
    for stage in stage_plan:
        cost[stage["start_month"]] += stage["stage_cost"]

    allocated_cost = sum(cost)
    residual_cost = total_cost - allocated_cost
    if abs(residual_cost) > EPS:
        cost[stage_plan[-1]["start_month"]] += residual_cost
        stage_plan[-1]["stage_cost"] += residual_cost

    # Hậu mãi
    if after_sales_total > 0 and warranty_months > 0:
        monthly_after_sales = after_sales_total / warranty_months
        for t in range(after_sales_start_month, after_sales_end_month + 1):
            after_sales[t] += monthly_after_sales

    # Thu hồi cuối kỳ
    salvage[horizon] += salvage_value_total

    # Hạn mức vay theo giai đoạn
    debt_limit_amount_by_stage = {i: 0.0 for i in range(1, 6)}
    for item in raw_debt_draw_schedule:
        stage_no = int(item["stage_no"])
        draw_pct_cost = float(item["draw_pct_cost"])

        if draw_pct_cost < 0:
            raise ValueError(f"Hạn mức vay giai đoạn {stage_no} không được âm.")
        if stage_no < 1 or stage_no > 4:
            raise ValueError("Hạn mức vay chỉ được phép từ giai đoạn 1 đến giai đoạn 4.")
        if stage_no > len(stage_plan):
            continue

        debt_limit_amount_by_stage[stage_no] += total_cost * (draw_pct_cost / 100.0)

    total_debt_limit_amount = sum(debt_limit_amount_by_stage.values())
    if total_debt_limit_amount - total_cost > EPS:
        raise ValueError("Tổng hạn mức vay không được lớn hơn tổng giá vốn.")

    stage_by_start_month = {stage["start_month"]: stage for stage in stage_plan}

    # =========================
    # 7. HÀM MÔ PHỎNG WATERFALL
    # =========================
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

        def calc_principal_due(month_idx, current_debt_balance):
            if current_debt_balance <= EPS:
                return 0.0

            if principal_repayment_mode == "Trả đều theo tháng":
                if 1 <= month_idx <= last_collection_month:
                    remaining_periods = last_collection_month - month_idx + 1
                    if remaining_periods > 0:
                        return current_debt_balance / remaining_periods
                return 0.0

            if principal_repayment_mode == "Trả toàn bộ tại tháng thu tiền cuối cùng của giai đoạn nghiệm thu cuối":
                if month_idx == last_collection_month:
                    return current_debt_balance
                return 0.0

            return 0.0

        def simulate_forward_no_distribution(start_month, starting_cash, starting_debt):
            sim_cash = float(starting_cash)
            sim_debt = float(starting_debt)
            future_equity_needed = 0.0

            for tt in range(start_month, horizon + 1):
                sim_cash += customer_advance[tt] + collections[tt] + salvage[tt]

                if tt in stage_by_start_month:
                    sim_stage = stage_by_start_month[tt]
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
                        sim_remaining_stage_cost = 0.0

                sim_interest_due = sim_debt * monthly_interest_rate if sim_debt > EPS else 0.0
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

            if sim_debt > EPS:
                future_equity_needed += sim_debt
                sim_debt = 0.0

            return future_equity_needed

        reserve_cache = {}

        def required_cash_reserve_from_next_month(next_month, current_debt_balance):
            if next_month > horizon:
                return 0.0

            cache_key = (next_month, round(current_debt_balance, 8))
            if cache_key in reserve_cache:
                return reserve_cache[cache_key]

            equity_need_at_zero_cash = simulate_forward_no_distribution(
                start_month=next_month,
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
                    start_month=next_month,
                    starting_cash=mid,
                    starting_debt=current_debt_balance,
                )
                if future_equity_needed <= EPS:
                    hi = mid
                else:
                    lo = mid

            reserve_cache[cache_key] = hi
            return hi

        for t in timeline:
            opening_cash_local[t] = cash_balance

            # 1) Tiền vào đầu tháng
            cash_balance += customer_advance[t] + collections[t] + salvage[t]

            # 2) Nếu đầu giai đoạn -> chi tiền đầu giai đoạn theo thứ tự:
            # tiền sẵn có/CĐT -> vay của giai đoạn đó -> VCSH
            if t in stage_by_start_month:
                stage = stage_by_start_month[t]
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
                    remaining_stage_cost = 0.0

                stage_cash_used_map[stage_no] = cash_used
                stage_debt_used_map[stage_no] = debt_used
                stage_equity_used_map[stage_no] = equity_used_for_stage

            peak_debt_local = max(peak_debt_local, debt_balance)

            # 3) Lãi tháng tính trên dư nợ sau draw đầu tháng
            interest_due = debt_balance * monthly_interest_rate if debt_balance > EPS else 0.0
            interest_local[t] = interest_due

            # 4) Trả gốc theo mode
            principal_due = calc_principal_due(t, debt_balance)

            # 5) Các chi phí khác trong tháng
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

            # 6) Phân phối tiền dư về VCSH:
            # giữ lại đúng reserve tối thiểu, chỉ trả phần vượt reserve
            if t < horizon and cash_balance > EPS:
                reserve_needed = required_cash_reserve_from_next_month(
                    next_month=t + 1,
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

    # Pass 1: chưa tính tax để lấy tổng lãi vay
    pass1 = run_waterfall(total_tax_at_horizon=0.0)
    total_interest_pass1 = pass1["total_interest"]

    # =========================
    # 8. THUẾ
    # =========================
    pre_tax_profit_equity = net_contract_value + salvage_value_total - total_cost - after_sales_total - total_interest_pass1
    total_cit = max(0.0, pre_tax_profit_equity) * cit_rate

    pre_tax_profit_project = net_contract_value + salvage_value_total - total_cost - after_sales_total
    project_tax_total = max(0.0, pre_tax_profit_project) * cit_rate
    project_tax[horizon] = project_tax_total

    # Pass 2: có tax thật
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

    # Gắn thông tin dùng vốn thực tế vào stage_plan
    for stage in stage_plan:
        stage_no = stage["stage_no"]
        stage["customer_cash_used_for_stage_cost"] = pass2["stage_cash_used_map"][stage_no]
        stage["actual_debt_draw"] = pass2["stage_debt_used_map"][stage_no]
        stage["actual_equity_for_stage_cost"] = pass2["stage_equity_used_map"][stage_no]

    total_actual_debt_draw = sum(debt_draw)

    # =========================
    # 9. AR, PROJECT CF, EQUITY CF
    # =========================
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

    # =========================
    # 10. CHỈ SỐ
    # =========================
    project_irr_month = safe_irr(project_cf)
    equity_irr_month = safe_irr(equity_cf)

    project_irr_annual = annualize_monthly_irr(project_irr_month)
    equity_irr_annual = annualize_monthly_irr(equity_irr_month)

    project_real_irr_annual = fisher_real_rate_pct(project_irr_annual, inflation_rate_pct)
    equity_real_irr_annual = fisher_real_rate_pct(equity_irr_annual, inflation_rate_pct)
    bank_real_rate_annual = fisher_real_rate_pct(bank_rate_pct, inflation_rate_pct)

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

    moic = equity_multiple

    net_profit = net_contract_value + salvage_value_total - total_cost - after_sales_total - total_interest - total_cit
    net_profit_margin = None
    if net_contract_value > EPS:
        net_profit_margin = (net_profit / net_contract_value) * 100.0

    real_irr_status, real_irr_spread_vs_bank, real_irr_explanation = classify_real_irr_vs_bank(
        equity_real_irr_annual,
        bank_real_rate_annual,
    )
    net_profit_margin_status, net_profit_margin_explanation = classify_net_profit_margin(net_profit_margin)
    moic_status, moic_explanation = classify_multiple(moic, "MOIC")
    equity_multiple_status, equity_multiple_explanation = classify_multiple(equity_multiple, "Equity Multiple")

    # Chỉ dùng một trục "multiple" trong quyết định để tránh double count vì MOIC = Equity Multiple trong mô hình hiện tại
    decision = aggregate_decision(real_irr_status, net_profit_margin_status, moic_status)

    decision_basis = (
        "Đánh giá sơ bộ hiện dựa trên 3 lớp: "
        "(1) IRR vốn chủ thực theo Fisher so với lãi suất ngân hàng thực; "
        "(2) Net Profit Margin; "
        "(3) MOIC/Equity Multiple. "
        "GO khi IRR thực vượt benchmark đủ tốt và các chỉ số còn lại không yếu; "
        "NO GO nếu IRR thực thua benchmark hoặc cả biên lợi nhuận lẫn multiple đều yếu; "
        "các trường hợp còn lại là REVIEW."
    )

    fisher_basis = (
        "IRR thực và lãi suất ngân hàng thực được quy đổi theo Fisher: "
        "real = ((1 + nominal) / (1 + inflation)) - 1. "
        "Việc đánh giá ưu tiên nhìn trên sức sinh lời thực sau khi loại ảnh hưởng của lạm phát."
    )

    net_profit_margin_basis = (
        "Net Profit Margin = Lợi nhuận ròng / Giá trị hợp đồng sau chiết khấu. "
        "Chỉ số này cho biết mỗi 100 đồng doanh thu thực nhận còn lại bao nhiêu đồng lợi nhuận ròng sau chi phí, lãi vay và thuế."
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

    if principal_repayment_mode == "Trả đều theo tháng":
        principal_repayment_basis = (
            "Trả gốc vay theo phương thức trả đều theo tháng. "
            "Mỗi tháng, số gốc phải trả được phân bổ đều trên số kỳ còn lại đến tháng thu tiền cuối cùng của giai đoạn nghiệm thu cuối."
        )
    else:
        principal_repayment_basis = (
            "Trả toàn bộ gốc vay tại tháng thu tiền cuối cùng của giai đoạn nghiệm thu cuối."
        )

    evaluation_table = [
        {
            "Nhóm đánh giá": "IRR thực vs lãi suất NH thực",
            "Kết quả": real_irr_status,
            "Diễn giải": real_irr_explanation,
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
        "project_irr_annual": project_irr_annual,
        "equity_irr_annual": equity_irr_annual,
        "project_real_irr_annual": project_real_irr_annual,
        "equity_real_irr_annual": equity_real_irr_annual,
        "bank_real_rate_annual": bank_real_rate_annual,
        "real_irr_spread_vs_bank": real_irr_spread_vs_bank,

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
        "fisher_basis": fisher_basis,
        "net_profit_margin_basis": net_profit_margin_basis,
        "multiple_basis": multiple_basis,
        "source_of_funds_basis": source_of_funds_basis,
        "principal_repayment_basis": principal_repayment_basis,

        "real_irr_status": real_irr_status,
        "net_profit_margin_status": net_profit_margin_status,
        "moic_status": moic_status,
        "equity_multiple_status": equity_multiple_status,
        "real_irr_explanation": real_irr_explanation,
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
        "last_collection_month": last_collection_month,
        "bank_rate_pct": bank_rate_pct,
        "inflation_rate_pct": inflation_rate_pct,
    }
