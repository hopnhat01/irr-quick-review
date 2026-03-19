import math
import numpy_financial as npf

def safe_irr(cashflows):
    """
    Hàm tính IRR an toàn: 
    - Check mảng rỗng
    - Check điều kiện đổi dấu (phải có âm và dương)
    - Check NaN hoặc nghiệm vô lý
    """
    if not cashflows:
        return None
    
    # Bắt buộc phải có dòng tiền âm (bỏ vốn) và dương (thu hồi) mới tính được IRR
    has_positive = any(cf > 0 for cf in cashflows)
    has_negative = any(cf < 0 for cf in cashflows)
    if not (has_positive and has_negative):
        return None
        
    try:
        irr = npf.irr(cashflows)
        # Bắt lỗi NaN hoặc IRR <= -100% (mất trắng)
        if irr is None or math.isnan(irr) or irr <= -1:
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
    # 1. TRÍCH XUẤT INPUT
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

    # 2. TÍNH TOÁN CƠ SỞ CHUẨN (BASE METRICS)
    total_cost = deal_value * cost_pct
    debt_target = total_cost * debt_pct
    
    # Xử lý delay_month dùng math.ceil an toàn hơn round thô
    delay_month = math.ceil(dso_days / 30.0)
    total_months = project_months + delay_month

    # KHỞI TẠO MẢNG DÒNG TIỀN (Thêm debt_draw)
    revenue = [0.0] * (total_months + 1)
    cost = [0.0] * (total_months + 1)
    debt_draw = [0.0] * (total_months + 1) # SỬA LỖI LỚN NHẤT: Thêm dòng tiền nhận nợ
    interest = [0.0] * (total_months + 1)
    principal = [0.0] * (total_months + 1)
    tax = [0.0] * (total_months + 1)
    salvage = [0.0] * (total_months + 1)
    equity_outflow = [0.0] * (total_months + 1)

    # 3. LOGIC DOANH THU (REVENUE)
    upfront_cash = 0.0
    if payment_type == "Trả trước":
        upfront_cash = deal_value * upfront_pct
        revenue_final = deal_value - upfront_cash
        revenue[0] += upfront_cash
        revenue[total_months] += revenue_final

    elif payment_type == "Theo tiến độ":
        revenue_progress_total = deal_value * progress_pct
        revenue_final = deal_value - revenue_progress_total
        revenue_progress_per_month = revenue_progress_total / project_months if project_months > 0 else 0
        for t in range(1, project_months + 1):
            revenue[t] += revenue_progress_per_month
        revenue[total_months] += revenue_final

    elif payment_type == "Trả sau":
        revenue[total_months] += deal_value

    # 4. LOGIC GIẢI NGÂN NỢ (DEBT DRAW) VÀ VỐN CHỦ (EQUITY)
    # Khách trả trước dùng để giảm nợ cần vay
    actual_debt = max(0.0, debt_target - upfront_cash)
    nominal_equity = total_cost - debt_target # Vốn danh nghĩa để report
    
    # Giả định giải ngân nợ ở T0 để có tiền làm dự án
    debt_draw[0] += actual_debt

    # 5. LOGIC CHI PHÍ (COST)
    if cost_timing == "Trả đều":
        cost_per_month = total_cost / project_months if project_months > 0 else 0
        for t in range(1, project_months + 1):
            cost[t] += cost_per_month
    elif cost_timing == "Trả đầu kỳ":
        cost[0] += total_cost
    elif cost_timing == "Trả cuối kỳ":
        cost[project_months] += total_cost

    # 6. LOGIC TRẢ GỐC VÀ LÃI (RECEIVABLE BRIDGE)
    monthly_rate = annual_interest_rate / 12.0
    interest_per_month = actual_debt * monthly_rate
    
    # SỬA LỖI TIMING: Trả lãi và gốc kéo dài đến tận lúc thu tiền (total_months)
    for t in range(1, total_months + 1):
        interest[t] += interest_per_month
    
    principal[total_months] += actual_debt # Trả gốc khi tiền về

    # 7. LOGIC THU HỒI VÀ THUẾ
    salvage_value = deal_value * salvage_pct
    salvage[total_months] += salvage_value

    total_revenue = deal_value
    total_interest = sum(interest)
    # Lá chắn thuế (Tax Shield): được trừ lãi vay trước khi tính thuế
    taxable_profit = total_revenue - total_cost - total_interest + salvage_value
    total_tax = max(0.0, taxable_profit) * tax_rate
    tax[total_months] += total_tax

    # 8. TÍNH DÒNG TIỀN RÒNG (NET CASH FLOW - EQUITY IRR)
    net_cf = []
    for t in range(total_months + 1):
        cf = (
            revenue[t] 
            + salvage[t] 
            + debt_draw[t] # Cộng tiền vay vào
            - cost[t] 
            - interest[t] 
            - principal[t] 
            - tax[t]
        )
        # KHÔNG trừ equity_outflow ở đây nữa để tránh Double Counting
        net_cf.append(cf)
        
        # Nếu dòng tiền tháng đó bị âm -> Đó chính là phần Vốn Chủ (Equity) thực sự phải bơm vào
        if cf < 0:
            equity_outflow[t] = abs(cf)

    # 9. DÒNG TIỀN TÍCH LŨY & CHỈ SỐ KHÁC
    cum_cf = []
    running = 0.0
    for cf in net_cf:
        running += cf
        cum_cf.append(running)

    # Tính IRR
    irr_month = safe_irr(net_cf)
    irr_annual = None
    if irr_month is not None:
        irr_annual = ((1 + irr_month) ** 12 - 1) * 100

    # Payback Period
    payback_month = None
    if cum_cf[0] >= 0 and all(v >= 0 for v in cum_cf):
        payback_month = 0 # Dự án tự tài trợ ngay từ đầu
    else:
        for i, value in enumerate(cum_cf):
            if value >= 0 and i > 0:
                payback_month = i
                break

    peak_cash_out = abs(min(min(cum_cf), 0.0))
    net_cash_t0 = net_cf[0]
    decision = get_decision(irr_annual)

    return {
        "timeline": list(range(total_months + 1)),
        "revenue": revenue,
        "debt_draw": debt_draw, # Biến mới để xuất ra bảng
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
        "equity": nominal_equity, 
    }
