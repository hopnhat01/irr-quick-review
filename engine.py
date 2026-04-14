import math

EPS = 1e-9
DAY_BASIS = 360.0
DAYS_PER_MONTH = 30.0
MONTHS_PER_YEAR = 12.0


def sign_change_count(cashflows):
    vals = [float(x) for x in cashflows if abs(float(x)) > EPS]
    if len(vals) < 2:
        return 0
    return sum((a > 0) != (b > 0) for a, b in zip(vals, vals[1:]))


def safe_irr(cashflows, times=None):
    if not cashflows or len(cashflows) < 2:
        return None

    vals = [float(x) for x in cashflows]
    has_positive = any(v > 0 for v in vals)
    has_negative = any(v < 0 for v in vals)
    if not (has_positive and has_negative):
        return None

    if times is None:
        time_points = [float(i) for i in range(len(vals))]
    else:
        if len(times) != len(vals):
            raise ValueError("times phải có cùng số phần tử với cashflows.")
        time_points = [float(t) for t in times]

    points = [(t, cf) for t, cf in zip(time_points, vals) if abs(cf) > EPS]
    if len(points) < 2:
        return None

    def npv(rate):
        if rate <= -1:
            return None
        try:
            log_base = math.log1p(rate)
            total = 0.0
            for t, cf in points:
                total += cf * math.exp(-t * log_base)
            return total
        except Exception:
            return None

    try:
        candidate_rates = [
            -0.9999,
            -0.99,
            -0.95,
            -0.90,
            -0.75,
            -0.50,
            -0.25,
            -0.10,
            0.0,
            0.02,
            0.05,
            0.10,
            0.20,
            0.50,
            1.0,
            2.0,
            5.0,
            10.0,
            20.0,
            50.0,
            100.0,
        ]

        npv_values = []
        for r in candidate_rates:
            npv_values.append((r, npv(r)))

        bracket = None
        for i in range(len(npv_values) - 1):
            r1, v1 = npv_values[i]
            r2, v2 = npv_values[i + 1]

            if v1 is None or v2 is None:
                continue

            if abs(v1) <= 1e-7:
                return float(r1)
            if abs(v2) <= 1e-7:
                return float(r2)

            if v1 * v2 < 0:
                bracket = (r1, r2, v1, v2)
                break

        if bracket is None:
            low = -0.999999
            high = 0.10

            npv_low = npv(low)
            npv_high = npv(high)
            if npv_low is None or npv_high is None:
                return None

            expand_steps = 0
            while npv_low * npv_high > 0 and expand_steps < 80:
                high = high * 2 + 0.10
                npv_high = npv(high)
                if npv_high is None:
                    return None
                expand_steps += 1

            if npv_low * npv_high > 0:
                return None

            bracket = (low, high, npv_low, npv_high)

        low, high, npv_low, _ = bracket

        for _ in range(300):
            mid = (low + high) / 2.0
            npv_mid = npv(mid)
            if npv_mid is None:
                return None

            if abs(npv_mid) <= 1e-7:
                return float(mid)

            if npv_low * npv_mid <= 0:
                high = mid
            else:
                low = mid
                npv_low = npv_mid

        return float((low + high) / 2.0)
    except Exception:
        return None


def annualize_monthly_irr(monthly_irr):
    if monthly_irr is None:
        return None
    return ((1 + monthly_irr) ** MONTHS_PER_YEAR - 1) * 100


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
    principal_repayment_mode = str(inputs.get("principal_repayment_mode", "Trả đều theo ngày"))
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
        "Trả đều theo ngày",
        "Trả toàn bộ tại ngày thu tiền cuối cùng của giai đoạn nghiệm thu cuối",
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

    if after_sales_total > 0 and warranty_days > 0:
        after_sales_start_day = last_stage_end + 1
        after_sales_end_day = last_stage_end + warranty_days
    else:
        after_sales_start_day = last_stage_end
        after_sales_end_day = last_stage_end

    horizon = max(last_collection_day, after_sales_end_day)
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

        def calc_principal_due(day_idx, current_debt_balance):
            if current_debt_balance <= EPS:
                return 0.0

            if principal_repayment_mode == "Trả đều theo ngày":
                if 1 <= day_idx <= last_collection_day:
                    remaining_days = last_collection_day - day_idx + 1
                    if remaining_days > 0:
                        return current_debt_balance / remaining_days
                return 0.0

            if principal_repayment_mode == "Trả toàn bộ tại ngày thu tiền cuối cùng của giai đoạn nghiệm thu cuối":
                if day_idx == last_collection_day:
                    return current_debt_balance
                return 0.0

            return 0.0

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

    project_cf_sign_changes = sign_change_count(project_cf)
    equity_cf_sign_changes = sign_change_count(equity_cf)

    project_irr_monthly = safe_irr(project_cf, time_in_months)
    equity_irr_monthly = safe_irr(equity_cf, time_in_months)

    project_irr_warning = None
    equity_irr_warning = None

    if project_cf_sign_changes > 1:
        project_irr_warning = (
            f"Project cash flow đổi dấu {project_cf_sign_changes} lần; "
            "IRR vẫn được tính theo nghiệm tìm thấy trong khoảng dò, nhưng có thể không duy nhất."
        )

    if equity_cf_sign_changes > 1:
        equity_irr_warning = (
            f"Equity cash flow đổi dấu {equity_cf_sign_changes} lần; "
            "IRR vẫn được tính theo nghiệm tìm thấy trong khoảng dò, nhưng có thể không duy nhất."
        )

    project_irr_annual = annualize_monthly_irr(project_irr_monthly)
    equity_irr_annual = annualize_monthly_irr(equity_irr_monthly)

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

    real_irr_status, real_irr_spread_vs_bank, real_irr_explanation = classify_real_irr_vs_bank(
        equity_real_irr_annual,
        bank_real_rate_annual,
    )
    net_profit_margin_status, net_profit_margin_explanation = classify_net_profit_margin(net_profit_margin)
    moic_status, moic_explanation = classify_multiple(moic, "MOIC")
    equity_multiple_status, equity_multiple_explanation = classify_multiple(equity_multiple, "Equity Multiple")

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

    irr_basis = (
        "IRR được tính theo hệ quy chiếu tháng lẻ: mỗi mốc thời gian được đổi thành số tháng bằng ngày/30, "
        "sau đó giải IRR theo mốc tháng và annualize theo công thức (1 + IRR_tháng)^12 - 1."
    )

    net_profit_margin_basis = (
        "Net Profit Margin = Lợi nhuận ròng từ hoạt động hợp đồng / Giá trị hợp đồng sau chiết khấu. "
        "Trong mô hình này, khi tính margin đã loại phần salvage khỏi tử số để tránh làm đẹp giả biên lợi nhuận ròng của hoạt động chính."
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

    if principal_repayment_mode == "Trả đều theo ngày":
        principal_repayment_basis = (
            "Trả gốc vay theo phương thức trả đều theo ngày. "
            "Mỗi ngày, số gốc phải trả được phân bổ đều trên số ngày còn lại đến ngày thu tiền cuối cùng của giai đoạn nghiệm thu cuối."
        )
    else:
        principal_repayment_basis = "Trả toàn bộ gốc vay tại ngày thu tiền cuối cùng của giai đoạn nghiệm thu cuối."

    interest_basis = (
        "Lãi vay được tính theo ngày trên dư nợ sau rút vay của chính ngày đó, với quy ước lãi suất năm/360. "
        "Nhờ vậy cách ghi nhận rút vay, lãi vay và trả gốc trong mô hình là nhất quán trên cùng một timeline."
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
        "project_irr_warning": project_irr_warning,
        "equity_irr_warning": equity_irr_warning,
        "project_irr_monthly": None if project_irr_monthly is None else project_irr_monthly * 100.0,
        "equity_irr_monthly": None if equity_irr_monthly is None else equity_irr_monthly * 100.0,
        "project_irr_annual": project_irr_annual,
        "equity_irr_annual": equity_irr_annual,
        "project_real_irr_annual": project_real_irr_annual,
        "equity_real_irr_annual": equity_real_irr_annual,
        "bank_real_rate_annual": bank_real_rate_annual,
        "real_irr_spread_vs_bank": real_irr_spread_vs_bank,
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
        "net_profit_margin_basis": net_profit_margin_basis,
        "multiple_basis": multiple_basis,
        "source_of_funds_basis": source_of_funds_basis,
        "principal_repayment_basis": principal_repayment_basis,
        "interest_basis": interest_basis,
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
        "last_collection_day": last_collection_day,
        "bank_rate_pct": bank_rate_pct,
        "inflation_rate_pct": inflation_rate_pct,
    }
