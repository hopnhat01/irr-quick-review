# app.py
import numbers

import pandas as pd
import streamlit as st

from engine import build_model


st.set_page_config(page_title="Công cụ ước tính hiệu quả deal", layout="wide")


DEFAULT_PASSWORD = "000"


def get_password():
    try:
        return st.secrets["APP_PASSWORD"]
    except Exception:
        return DEFAULT_PASSWORD


PASSWORD = get_password()


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("Truy cập hệ thống")

        password_input = st.text_input("Nhập mật khẩu", type="password")

        if st.button("Xác nhận"):
            if password_input == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Sai mật khẩu")

        st.stop()


def format_vn(number, decimals=2):
    if number is None or pd.isna(number):
        return "-"
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_optional_int(value, field_name):
    text = str(value).strip().replace(",", ".")
    if text == "":
        return None
    try:
        num = float(text)
        if not num.is_integer():
            raise ValueError
        return int(num)
    except Exception as exc:
        raise ValueError(f"{field_name} phải là số nguyên.") from exc


def parse_optional_float(value, field_name):
    text = str(value).strip().replace(",", ".")
    if text == "":
        return None
    try:
        return float(text)
    except Exception as exc:
        raise ValueError(f"{field_name} phải là số.") from exc


def format_money_series(df, exclude_cols=None):
    exclude_cols = exclude_cols or []
    df_display = df.copy()
    for col in df_display.columns:
        if col in exclude_cols:
            continue
        df_display[col] = df_display[col].apply(
            lambda x: format_vn(x, 0) if isinstance(x, numbers.Number) and not pd.isna(x) else x
        )
    return df_display


check_password()

st.title("Công cụ ước tính hiệu quả deal")

with st.expander("Giải thích nhanh cách nhập liệu", expanded=False):
    st.write("1) Giá trị hợp đồng nhập ở đây là giá trị hợp đồng gốc trước chiết khấu.")
    st.write("2) Chiết khấu hợp đồng được nhập theo % giá trị hợp đồng gốc và sẽ làm giảm doanh thu thực nhận.")
    st.write("3) Tạm ứng CĐT ban đầu + tổng các thanh toán giai đoạn phải bằng đúng 100% giá trị hợp đồng sau chiết khấu.")
    st.write("4) Giai đoạn nghiệm thu tối đa 5 giai đoạn, có thể để trống các giai đoạn cuối.")
    st.write("5) Mỗi giai đoạn cần nhập thời lượng thi công (ngày), tỷ lệ thanh toán (% giá trị hợp đồng sau chiết khấu) và tỷ lệ chi tiền đầu giai đoạn (% giá vốn).")
    st.write("6) Tổng tỷ lệ chi tiền đầu các giai đoạn phải bằng đúng 100% giá vốn.")
    st.write("7) Hạn mức vay theo giai đoạn được nhập theo % giá vốn. Hệ thống ưu tiên dùng tiền sẵn có từ CĐT/thu trước đó trước, phần thiếu mới rút vay, phần thiếu còn lại mới dùng VCSH.")
    st.write("8) Có 2 kiểu trả gốc vay: trả định kỳ vào cuối tháng hoặc trả toàn bộ vào ngày cuối cùng của tháng cuối cùng chứa kỳ thanh toán cuối.")
    st.write("9) Lãi vay được nhập theo năm, sau đó quy đổi về ngày theo tham chiếu lãi suất năm / 360.")
    st.write("10) IRR được tính trên trục tháng lẻ: mỗi mốc thời gian dùng số tháng = số ngày / 30. Hệ thống quét nhiều nghiệm và chọn nghiệm tài chính phù hợp nhất.")
    st.write("11) MIRR và NPV được bổ sung để hỗ trợ ra quyết định; IRR chỉ dùng để hiển thị tham khảo.")
    st.write("12) Lạm phát và lãi suất ngân hàng benchmark được dùng để quy đổi chỉ tiêu thực theo Fisher và để chiết khấu NPV benchmark.")
    st.write("13) MOIC / Equity Multiple và Net Profit Margin vẫn được giữ trong bộ đánh giá sơ bộ.")

st.subheader("1. Thông tin cơ bản")

deal_value = st.number_input(
    "Giá trị hợp đồng gốc (VND)",
    min_value=0,
    value=10_000_000_000,
    step=1_000_000,
    format="%d",
    help="Tổng giá trị hợp đồng trước khi áp dụng chiết khấu.",
)
st.caption("Hiển thị: " + format_vn(deal_value, 0) + " đ")

contract_discount_pct = st.number_input(
    "Chiết khấu hợp đồng (% theo giá trị hợp đồng gốc)",
    min_value=0.0,
    max_value=100.0,
    value=0.0,
    step=0.1,
    help="Chiết khấu làm giảm doanh thu thực nhận từ khách hàng.",
)
st.caption("Hiển thị: " + format_vn(contract_discount_pct, 2) + " %")

cost_pct = st.number_input(
    "Tỷ lệ giá vốn (% theo giá trị hợp đồng gốc)",
    min_value=0.0,
    max_value=100.0,
    value=70.0,
    step=0.1,
)
st.caption("Hiển thị: " + format_vn(cost_pct, 2) + " %")

salvage_pct = st.number_input(
    "Giá trị thu hồi cuối kỳ (% theo giá trị hợp đồng gốc)",
    min_value=0.0,
    max_value=100.0,
    value=0.0,
    step=0.1,
)
st.caption("Hiển thị: " + format_vn(salvage_pct, 2) + " %")

tax_rate = st.number_input(
    "Thuế CIT (%)",
    min_value=0.0,
    max_value=100.0,
    value=20.0,
    step=0.1,
    help="Thuế thu nhập doanh nghiệp (Corporate Income Tax).",
)
st.caption("Hiển thị: " + format_vn(tax_rate, 2) + " %")

avg_dso_days = st.number_input(
    "Số ngày công nợ trung bình sau mỗi lần nghiệm thu",
    min_value=0,
    value=30,
    step=1,
    format="%d",
)
st.caption("Hiển thị: " + format_vn(avg_dso_days, 0) + " ngày")

discount_amount_preview = deal_value * contract_discount_pct / 100.0
net_contract_value_preview = deal_value - discount_amount_preview
total_cost_preview = deal_value * cost_pct / 100.0
salvage_preview = deal_value * salvage_pct / 100.0

col_basic_1, col_basic_2, col_basic_3, col_basic_4 = st.columns(4)
col_basic_1.metric("Chiết khấu hợp đồng", format_vn(discount_amount_preview, 0) + " đ")
col_basic_2.metric("Giá trị hợp đồng sau CK", format_vn(net_contract_value_preview, 0) + " đ")
col_basic_3.metric("Tổng giá vốn ước tính", format_vn(total_cost_preview, 0) + " đ")
col_basic_4.metric("Giá trị thu hồi cuối kỳ", format_vn(salvage_preview, 0) + " đ")

st.subheader("2. Nguồn vốn và benchmark")

owner_advance_pct = st.number_input(
    "Tỷ lệ tạm ứng chủ đầu tư ban đầu (% theo giá trị hợp đồng sau chiết khấu)",
    min_value=0.0,
    max_value=100.0,
    value=10.0,
    step=0.1,
    help="Khoản tạm ứng ban đầu của chủ đầu tư, tính trên giá trị hợp đồng sau chiết khấu.",
)
st.caption("Hiển thị: " + format_vn(owner_advance_pct, 2) + " %")

interest_rate = st.number_input(
    "Lãi suất vay năm (%)",
    min_value=0.0,
    max_value=100.0,
    value=12.0,
    step=0.1,
    help="Hệ thống quy đổi về lãi ngày theo annual / 360.",
)
st.caption("Hiển thị: " + format_vn(interest_rate, 2) + " %")

bank_rate_pct = st.number_input(
    "Lãi suất ngân hàng benchmark năm (%) để so sánh / chiết khấu NPV",
    min_value=0.0,
    max_value=100.0,
    value=6.0,
    step=0.1,
    help="Dùng làm benchmark cho NPV và MIRR / Fisher real comparison.",
)
st.caption("Hiển thị: " + format_vn(bank_rate_pct, 2) + " %")

inflation_rate_pct = st.number_input(
    "Lạm phát năm (%)",
    min_value=0.0,
    max_value=100.0,
    value=4.0,
    step=0.1,
    help="Dùng để quy đổi lãi suất danh nghĩa sang lãi suất thực theo Fisher.",
)
st.caption("Hiển thị: " + format_vn(inflation_rate_pct, 2) + " %")

principal_repayment_mode = st.selectbox(
    "Phương thức trả gốc vay",
    options=[
        "Trả định kỳ theo tháng",
        "Trả hết một lần ở ngày cuối cùng của tháng cuối cùng của giai đoạn thanh toán cuối cùng",
    ],
    index=0,
)

owner_advance_amount_preview = net_contract_value_preview * owner_advance_pct / 100.0
daily_interest_rate_preview = interest_rate / 100.0 / 360.0 * 100.0

col_capital_1, col_capital_2, col_capital_3 = st.columns(3)
col_capital_1.metric("Giá trị tạm ứng CĐT ban đầu", format_vn(owner_advance_amount_preview, 0) + " đ")
col_capital_2.metric(
    "Lãi suất NH thực theo Fisher",
    format_vn((((1 + bank_rate_pct / 100.0) / (1 + inflation_rate_pct / 100.0)) - 1) * 100, 2) + " %",
)
col_capital_3.metric(
    "Lãi vay ngày (annual / 360)",
    format_vn(daily_interest_rate_preview, 4) + " %",
)

st.subheader("3. Các giai đoạn nghiệm thu")

st.caption(
    "Nhập tối đa 5 giai đoạn. Có thể để trống các giai đoạn cuối. "
    "Mỗi giai đoạn gồm thời lượng thi công (ngày), tỷ lệ thanh toán (% theo giá trị hợp đồng sau chiết khấu) "
    "và tỷ lệ chi tiền ra ở đầu giai đoạn (% theo tổng giá vốn). "
    "Lưu ý: tạm ứng CĐT ban đầu + tổng các thanh toán giai đoạn phải bằng 100%."
)

default_stage_names = [
    "Giai đoạn 1",
    "Giai đoạn 2",
    "Giai đoạn 3",
    "Giai đoạn 4",
    "Giai đoạn 5",
]
default_stage_duration = ["60", "90", "60", "", ""]
default_stage_payment = ["20", "40", "30", "", ""]
default_stage_cost_out = ["30", "40", "30", "", ""]

stage_names = []
stage_duration_raw = []
stage_payment_raw = []
stage_cost_out_raw = []

header_cols = st.columns([2.1, 1.1, 1.4, 1.6])
header_cols[0].markdown("**Tên giai đoạn**")
header_cols[1].markdown("**Thời gian (ngày)**")
header_cols[2].markdown("**Thanh toán (% HĐ sau chiết khấu)**")
header_cols[3].markdown("**Chi tiền đầu kỳ (% giá vốn)**")

for i in range(5):
    cols = st.columns([2.1, 1.1, 1.4, 1.6])

    with cols[0]:
        stage_name = st.text_input(
            f"Tên giai đoạn {i + 1}",
            value=default_stage_names[i],
            key=f"stage_name_{i + 1}",
            label_visibility="collapsed",
        )

    with cols[1]:
        duration_text = st.text_input(
            f"Thời gian giai đoạn {i + 1}",
            value=default_stage_duration[i],
            key=f"stage_duration_{i + 1}",
            help="Có thể để trống nếu không dùng giai đoạn này.",
            label_visibility="collapsed",
            placeholder="Để trống nếu không dùng",
        )

    with cols[2]:
        payment_text = st.text_input(
            f"Thanh toán giai đoạn {i + 1}",
            value=default_stage_payment[i],
            key=f"stage_payment_{i + 1}",
            help="Tỷ lệ thanh toán của khách ở giai đoạn này (% theo giá trị hợp đồng sau chiết khấu).",
            label_visibility="collapsed",
            placeholder="Để trống nếu không dùng",
        )

    with cols[3]:
        cost_out_text = st.text_input(
            f"Chi tiền đầu kỳ giai đoạn {i + 1}",
            value=default_stage_cost_out[i],
            key=f"stage_cost_out_{i + 1}",
            help="Tỷ lệ chi tiền ra ở đầu giai đoạn này (% theo tổng giá vốn).",
            label_visibility="collapsed",
            placeholder="Để trống nếu không dùng",
        )

    stage_names.append(stage_name)
    stage_duration_raw.append(duration_text)
    stage_payment_raw.append(payment_text)
    stage_cost_out_raw.append(cost_out_text)

st.subheader("4. Hạn mức vay theo giai đoạn")

st.caption(
    "Tối đa 4 hạn mức vay, tương ứng với các giai đoạn 1 đến 4. "
    "Các tỷ lệ này nhập theo % giá vốn. Hệ thống sẽ chỉ rút vay khi chi đầu giai đoạn "
    "vượt quá tiền sẵn có từ CĐT/thu trước đó."
)

default_loan_draw_raw = ["20", "20", "", ""]
loan_draw_raw = []

loan_cols = st.columns(4)
for i in range(4):
    with loan_cols[i]:
        draw_text = st.text_input(
            f"Hạn mức vay GĐ{i + 1} (% giá vốn)",
            value=default_loan_draw_raw[i],
            key=f"loan_draw_{i + 1}",
            placeholder="Để trống nếu không dùng",
        )
        loan_draw_raw.append(draw_text)

st.subheader("5. Hậu mãi / bảo hành / bảo hiểm")

after_sales_pct = st.number_input(
    "Chi phí bảo hành / bảo hiểm hậu mãi (% theo giá trị hợp đồng gốc)",
    min_value=0.0,
    max_value=100.0,
    value=5.0,
    step=0.1,
)
st.caption("Hiển thị: " + format_vn(after_sales_pct, 2) + " %")

warranty_days = st.number_input(
    "Thời hạn bảo hành / hậu mãi (ngày)",
    min_value=0,
    value=360,
    step=1,
    format="%d",
)
st.caption("Hiển thị: " + format_vn(warranty_days, 0) + " ngày")

after_sales_amount_preview = deal_value * after_sales_pct / 100.0
st.metric("Tổng chi phí hậu mãi ước tính", format_vn(after_sales_amount_preview, 0) + " đ")

run_button = st.button("Tính kết quả")

if run_button:
    try:
        errors = []

        stages = []
        blank_stage_started = False

        for i in range(5):
            stage_no = i + 1
            stage_name = stage_names[i].strip() if stage_names[i].strip() else f"Giai đoạn {stage_no}"

            duration_days = parse_optional_int(stage_duration_raw[i], f"Thời gian giai đoạn {stage_no}")
            payment_pct = parse_optional_float(stage_payment_raw[i], f"Thanh toán giai đoạn {stage_no}")
            cost_out_pct = parse_optional_float(stage_cost_out_raw[i], f"Chi tiền đầu giai đoạn {stage_no}")

            if duration_days is None and payment_pct is None and cost_out_pct is None:
                blank_stage_started = True
                continue

            if blank_stage_started:
                errors.append("Các giai đoạn nghiệm thu phải được nhập liên tục từ giai đoạn 1, không được bỏ trống ở giữa.")

            filled_count = sum(x is not None for x in [duration_days, payment_pct, cost_out_pct])
            if filled_count not in (0, 3):
                errors.append(
                    f"Giai đoạn {stage_no} phải nhập đủ 3 trường: thời gian, thanh toán (% HĐ sau CK) và chi tiền đầu giai đoạn (% giá vốn)."
                )
                continue

            if duration_days is not None and duration_days <= 0:
                errors.append(f"Thời gian của giai đoạn {stage_no} phải lớn hơn 0 ngày.")
            if payment_pct is not None and payment_pct <= 0:
                errors.append(f"Tỷ lệ thanh toán của giai đoạn {stage_no} phải lớn hơn 0%.")
            if payment_pct is not None and payment_pct > 100:
                errors.append(f"Tỷ lệ thanh toán của giai đoạn {stage_no} không thể lớn hơn 100%.")
            if cost_out_pct is not None and cost_out_pct <= 0:
                errors.append(f"Tỷ lệ chi tiền đầu giai đoạn {stage_no} phải lớn hơn 0% giá vốn.")
            if cost_out_pct is not None and cost_out_pct > 100:
                errors.append(f"Tỷ lệ chi tiền đầu giai đoạn {stage_no} không thể lớn hơn 100% giá vốn.")

            stages.append(
                {
                    "stage_no": stage_no,
                    "name": stage_name,
                    "duration_days": duration_days,
                    "payment_pct": payment_pct,
                    "cost_out_pct": cost_out_pct,
                }
            )

        if len(stages) == 0:
            errors.append("Phải nhập ít nhất 1 giai đoạn nghiệm thu.")

        total_project_days = sum(stage["duration_days"] for stage in stages) if stages else 0
        total_stage_payment_pct = sum(stage["payment_pct"] for stage in stages) if stages else 0.0
        total_customer_payment_pct = owner_advance_pct + total_stage_payment_pct
        total_cost_out_pct = sum(stage["cost_out_pct"] for stage in stages) if stages else 0.0

        if stages and abs(total_customer_payment_pct - 100.0) > 1e-6:
            errors.append(
                "Tỷ lệ tạm ứng chủ đầu tư ban đầu + tổng tỷ lệ thanh toán của các giai đoạn phải bằng đúng 100% giá trị hợp đồng sau chiết khấu."
            )

        if stages and abs(total_cost_out_pct - 100.0) > 1e-6:
            errors.append("Tổng tỷ lệ chi tiền đầu các giai đoạn phải bằng đúng 100% giá vốn.")

        debt_draw_schedule = []
        blank_loan_started = False

        for i in range(4):
            stage_no = i + 1
            draw_pct_cost = parse_optional_float(loan_draw_raw[i], f"Hạn mức vay giai đoạn {stage_no}")

            if draw_pct_cost is None:
                blank_loan_started = True
                continue

            if blank_loan_started:
                errors.append("Các hạn mức vay phải nhập liên tục từ giai đoạn 1.")
            if draw_pct_cost < 0:
                errors.append(f"Hạn mức vay giai đoạn {stage_no} không được âm.")
            if draw_pct_cost > 100:
                errors.append(f"Hạn mức vay giai đoạn {stage_no} không thể lớn hơn 100% giá vốn.")
            if stage_no > len(stages):
                errors.append(
                    f"Không thể nhập hạn mức vay ở giai đoạn {stage_no} khi dự án chỉ có {len(stages)} giai đoạn nghiệm thu."
                )

            debt_draw_schedule.append(
                {
                    "stage_no": stage_no,
                    "draw_pct_cost": draw_pct_cost,
                }
            )

        total_debt_draw_pct = sum(item["draw_pct_cost"] for item in debt_draw_schedule) if debt_draw_schedule else 0.0
        if total_debt_draw_pct > 100:
            errors.append("Tổng hạn mức vay không thể lớn hơn 100% giá vốn.")

        if contract_discount_pct > 100:
            errors.append("Chiết khấu hợp đồng không thể lớn hơn 100% giá trị hợp đồng.")
        if cost_pct > 100:
            errors.append("Tỷ lệ giá vốn không thể lớn hơn 100%.")
        if salvage_pct > 100:
            errors.append("Giá trị thu hồi cuối kỳ không thể lớn hơn 100% giá trị hợp đồng.")
        if tax_rate > 100:
            errors.append("Thuế CIT không thể lớn hơn 100%.")
        if owner_advance_pct > 100:
            errors.append("Tỷ lệ tạm ứng chủ đầu tư ban đầu không thể lớn hơn 100% giá trị hợp đồng sau chiết khấu.")
        if after_sales_pct > 100:
            errors.append("Chi phí bảo hành / bảo hiểm hậu mãi không thể lớn hơn 100% giá trị hợp đồng.")
        if bank_rate_pct > 100:
            errors.append("Lãi suất ngân hàng benchmark không thể lớn hơn 100%.")
        if inflation_rate_pct > 100:
            errors.append("Lạm phát không thể lớn hơn 100%.")
        if warranty_days < 0:
            errors.append("Thời hạn bảo hành / hậu mãi không được âm.")

        if errors:
            for err in errors:
                st.error(err)
            st.stop()

        inputs = {
            "deal_value": float(deal_value),
            "contract_discount_pct": float(contract_discount_pct),
            "cost_pct": float(cost_pct),
            "salvage_pct": float(salvage_pct),
            "tax_rate": float(tax_rate),
            "avg_dso_days": int(avg_dso_days),
            "owner_advance_pct": float(owner_advance_pct),
            "interest_rate": float(interest_rate),
            "bank_rate_pct": float(bank_rate_pct),
            "inflation_rate_pct": float(inflation_rate_pct),
            "principal_repayment_mode": principal_repayment_mode,
            "stages": stages,
            "debt_draw_schedule": debt_draw_schedule,
            "after_sales_pct": float(after_sales_pct),
            "warranty_days": int(warranty_days),
            "total_project_days": int(total_project_days),
        }

        with st.expander("Dữ liệu đầu vào đã chuẩn hóa"):
            st.json(inputs)

        result = build_model(inputs)

        st.subheader("Kết quả")

        equity_irr = result.get("equity_irr_annual")
        project_irr = result.get("project_irr_annual")
        equity_irr_monthly = result.get("equity_irr_monthly")
        project_irr_monthly = result.get("project_irr_monthly")
        equity_real_irr = result.get("equity_real_irr_annual")
        project_real_irr = result.get("project_real_irr_annual")

        equity_mirr = result.get("equity_mirr_annual")
        project_mirr = result.get("project_mirr_annual")
        equity_mirr_monthly = result.get("equity_mirr_monthly")
        project_mirr_monthly = result.get("project_mirr_monthly")
        equity_real_mirr = result.get("equity_real_mirr_annual")
        project_real_mirr = result.get("project_real_mirr_annual")
        bank_real_rate_annual = result.get("bank_real_rate_annual")
        real_mirr_spread_vs_bank = result.get("real_mirr_spread_vs_bank")

        equity_npv = result.get("equity_npv")
        project_npv = result.get("project_npv")

        payback_day = result.get("payback_day")
        payback_message = result.get("payback_message")
        peak_equity = result.get("peak_equity_at_risk")
        peak_debt = result.get("peak_debt")
        total_cost = result.get("total_cost")

        equity_multiple = result.get("equity_multiple")
        moic = result.get("moic")
        net_profit = result.get("net_profit")
        net_profit_margin = result.get("net_profit_margin")
        total_interest = result.get("total_interest")
        total_cit = result.get("total_cit")
        contract_discount_amount = result.get("contract_discount_amount")
        net_contract_value = result.get("net_contract_value")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("IRR vốn công ty (annualized)", format_vn(equity_irr, 2) + " %" if equity_irr is not None else "Không tính được")
            st.caption("IRR tháng: " + (format_vn(equity_irr_monthly, 4) + " %" if equity_irr_monthly is not None else "Không tính được"))
        with col2:
            st.metric("MIRR vốn công ty (annualized)", format_vn(equity_mirr, 2) + " %" if equity_mirr is not None else "Không tính được")
            st.caption("MIRR tháng: " + (format_vn(equity_mirr_monthly, 4) + " %" if equity_mirr_monthly is not None else "Không tính được"))
        with col3:
            st.metric("MIRR vốn công ty thực", format_vn(equity_real_mirr, 2) + " %" if equity_real_mirr is not None else "Không tính được")
        with col4:
            st.metric(
                "Spread MIRR thực - LS NH thực",
                format_vn(real_mirr_spread_vs_bank, 2) + " điểm %" if real_mirr_spread_vs_bank is not None else "Không tính được",
            )

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("IRR dự án (annualized)", format_vn(project_irr, 2) + " %" if project_irr is not None else "Không tính được")
            st.caption("IRR tháng: " + (format_vn(project_irr_monthly, 4) + " %" if project_irr_monthly is not None else "Không tính được"))
        with col6:
            st.metric("MIRR dự án (annualized)", format_vn(project_mirr, 2) + " %" if project_mirr is not None else "Không tính được")
            st.caption("MIRR tháng: " + (format_vn(project_mirr_monthly, 4) + " %" if project_mirr_monthly is not None else "Không tính được"))
        with col7:
            st.metric("Lãi suất NH thực", format_vn(bank_real_rate_annual, 2) + " %" if bank_real_rate_annual is not None else "Không tính được")
        with col8:
            st.metric("Thời gian hoàn vốn", f"{payback_day} ngày" if payback_day is not None else "Chưa hoàn vốn")

        col9, col10, col11, col12 = st.columns(4)
        col9.metric("NPV vốn công ty", format_vn(equity_npv, 0) + " đ" if equity_npv is not None else "Không tính được")
        col10.metric("NPV dự án", format_vn(project_npv, 0) + " đ" if project_npv is not None else "Không tính được")
        col11.metric("Net Profit Margin", format_vn(net_profit_margin, 2) + " %" if net_profit_margin is not None else "Không tính được")
        col12.metric("IRR vốn công ty thực", format_vn(equity_real_irr, 2) + " %" if equity_real_irr is not None else "Không tính được")

        col13, col14, col15, col16 = st.columns(4)
        col13.metric("Equity Multiple", format_vn(equity_multiple, 2) + "x" if equity_multiple is not None else "Không tính được")
        col14.metric("MOIC", format_vn(moic, 2) + "x" if moic is not None else "Không tính được")
        col15.metric("Vốn công ty phải bỏ ra thời điểm lớn nhất", format_vn(peak_equity, 0) + " đ" if peak_equity is not None else "-")
        col16.metric("Dư nợ vay lớn nhất", format_vn(peak_debt, 0) + " đ" if peak_debt is not None else "-")

        col17, col18, col19, col20 = st.columns(4)
        col17.metric("Giá trị HĐ sau chiết khấu", format_vn(net_contract_value, 0) + " đ" if net_contract_value is not None else "-")
        col18.metric("Tổng chiết khấu hợp đồng", format_vn(contract_discount_amount, 0) + " đ" if contract_discount_amount is not None else "-")
        col19.metric("Lợi nhuận ròng ước tính", format_vn(net_profit, 0) + " đ" if net_profit is not None else "-")
        col20.metric("Tổng giá vốn", format_vn(total_cost, 0) + " đ" if total_cost is not None else "-")

        col21, col22, col23 = st.columns(3)
        col21.metric("Tổng lãi vay", format_vn(total_interest, 0) + " đ" if total_interest is not None else "-")
        col22.metric("Thuế CIT", format_vn(total_cit, 0) + " đ" if total_cit is not None else "-")
        col23.metric("MIRR dự án thực", format_vn(project_real_mirr, 2) + " %" if project_real_mirr is not None else "Không tính được")

        project_irr_warning = result.get("project_irr_warning")
        equity_irr_warning = result.get("equity_irr_warning")
        if project_irr_warning:
            st.warning("Cảnh báo IRR dự án: " + project_irr_warning)
        if equity_irr_warning:
            st.warning("Cảnh báo IRR vốn công ty: " + equity_irr_warning)

        decision = result.get("decision")
        if decision == "GO":
            st.success("Đánh giá sơ bộ: GO - Nên làm")
        elif decision == "REVIEW":
            st.warning("Đánh giá sơ bộ: REVIEW - Cần xem lại")
        elif decision == "NO GO":
            st.error("Đánh giá sơ bộ: NO GO - Không nên làm")

        decision_basis = result.get("decision_basis")
        if decision_basis:
            st.caption(decision_basis)

        fisher_basis = result.get("fisher_basis")
        if fisher_basis:
            st.caption(fisher_basis)

        irr_basis = result.get("irr_basis")
        if irr_basis:
            st.caption(irr_basis)

        mirr_basis = result.get("mirr_basis")
        if mirr_basis:
            st.caption(mirr_basis)

        npv_basis = result.get("npv_basis")
        if npv_basis:
            st.caption(npv_basis)

        source_logic_basis = result.get("source_of_funds_basis")
        if source_logic_basis:
            st.caption(source_logic_basis)

        repayment_basis = result.get("principal_repayment_basis")
        if repayment_basis:
            st.caption(repayment_basis)

        interest_basis = result.get("interest_basis")
        if interest_basis:
            st.caption(interest_basis)

        if payback_message:
            if payback_day is None:
                st.info(payback_message)
            else:
                st.caption(payback_message)

        st.subheader("Giải thích các trụ đánh giá")

        real_mirr_explanation = result.get("real_mirr_explanation")
        if real_mirr_explanation:
            st.write("**1. MIRR vốn công ty thực vs lãi suất NH thực**")
            st.write(real_mirr_explanation)

        npv_explanation = result.get("npv_explanation")
        if npv_explanation:
            st.write("**2. NPV vốn công ty**")
            st.write(npv_explanation)

        net_profit_margin_explanation = result.get("net_profit_margin_explanation")
        if net_profit_margin_explanation:
            st.write("**3. Net Profit Margin**")
            st.write(net_profit_margin_explanation)

        moic_explanation = result.get("moic_explanation")
        if moic_explanation:
            st.write("**4. MOIC**")
            st.write(moic_explanation)

        equity_multiple_explanation = result.get("equity_multiple_explanation")
        if equity_multiple_explanation:
            st.write("**5. Equity Multiple**")
            st.write(equity_multiple_explanation)

        if result.get("evaluation_table"):
            st.subheader("Bảng đánh giá sơ bộ")
            eval_df = pd.DataFrame(result["evaluation_table"])
            st.dataframe(eval_df, use_container_width=True)

        if result.get("stage_plan"):
            st.subheader("Kế hoạch các giai đoạn")
            stage_df = pd.DataFrame(result["stage_plan"])

            rename_map = {
                "stage_no": "STT",
                "name": "Giai đoạn",
                "duration_days": "Thời gian (ngày)",
                "start_day": "Ngày bắt đầu",
                "end_day": "Ngày kết thúc",
                "collection_day": "Ngày thu tiền",
                "payment_pct": "Thanh toán (% HĐ sau chiết khấu)",
                "cost_out_pct": "Chi tiền đầu kỳ (% GV)",
                "revenue_share_pct": "Tỷ trọng phân bổ doanh thu (%)",
                "gross_contract_billing_value": "Billing gốc trước CK",
                "stage_discount_amount": "Chiết khấu phân bổ",
                "net_stage_billing_value": "Billing sau CK",
                "advance_offset": "Cấn trừ tạm ứng",
                "net_collection_value": "Thu tiền thực tế",
                "stage_cost": "Chi phí đầu kỳ",
                "customer_cash_used_for_stage_cost": "Dùng tiền sẵn có/CĐT",
                "actual_debt_draw": "Rút vay thực tế",
                "actual_equity_for_stage_cost": "VCSH cho chi đầu kỳ",
            }
            stage_df_display = stage_df.rename(columns=rename_map)

            money_cols = [
                "Billing gốc trước CK",
                "Chiết khấu phân bổ",
                "Billing sau CK",
                "Cấn trừ tạm ứng",
                "Thu tiền thực tế",
                "Chi phí đầu kỳ",
                "Dùng tiền sẵn có/CĐT",
                "Rút vay thực tế",
                "VCSH cho chi đầu kỳ",
            ]
            pct_cols = [
                "Thanh toán (% HĐ sau chiết khấu)",
                "Chi tiền đầu kỳ (% GV)",
                "Tỷ trọng phân bổ doanh thu (%)",
            ]

            for col in money_cols:
                if col in stage_df_display.columns:
                    stage_df_display[col] = stage_df_display[col].apply(lambda x: format_vn(x, 0))

            for col in pct_cols:
                if col in stage_df_display.columns:
                    stage_df_display[col] = stage_df_display[col].apply(lambda x: format_vn(x, 2) + " %")

            st.dataframe(stage_df_display, use_container_width=True)

        if result.get("timeline") and result.get("equity_cf"):
            st.subheader("Biểu đồ dòng tiền vốn công ty")
            chart_df = pd.DataFrame(
                {
                    "Ngày": result["timeline"],
                    "Dòng tiền vốn công ty": result["equity_cf"],
                }
            ).set_index("Ngày")
            st.line_chart(chart_df)

        if result.get("timeline") and result.get("cum_equity_cf"):
            st.subheader("Biểu đồ dòng tiền vốn công ty lũy kế")
            cum_chart_df = pd.DataFrame(
                {
                    "Ngày": result["timeline"],
                    "Dòng tiền vốn công ty lũy kế": result["cum_equity_cf"],
                }
            ).set_index("Ngày")
            st.line_chart(cum_chart_df)

        cashflow_keys = [
            "timeline",
            "customer_advance",
            "collections",
            "debt_draw",
            "cost",
            "after_sales",
            "interest",
            "principal",
            "tax",
            "salvage",
            "equity_in",
            "equity_out",
            "equity_cf",
        ]

        if all(key in result for key in cashflow_keys):
            st.subheader("Bảng dòng tiền")

            df = pd.DataFrame(
                {
                    "Ngày": result["timeline"],
                    "Tháng quy đổi": result.get("time_in_months"),
                    "Tạm ứng CĐT": result["customer_advance"],
                    "Thu tiền nghiệm thu": result["collections"],
                    "Rút vay thực tế": result["debt_draw"],
                    "Chi phí đầu giai đoạn": result["cost"],
                    "Chi phí hậu mãi": result["after_sales"],
                    "Lãi vay": result["interest"],
                    "Trả gốc": result["principal"],
                    "Thuế CIT": result["tax"],
                    "Thu hồi cuối kỳ": result["salvage"],
                    "Vốn công bơm vào": result["equity_in"],
                    "Tiền trả về vốn công ty": result["equity_out"],
                    "Dòng tiền vốn công ty": result["equity_cf"],
                }
            )

            if "debt_balance" in result:
                df["Dư nợ cuối ngày"] = result["debt_balance"]
            if "closing_cash" in result:
                df["Tiền cuối ngày"] = result["closing_cash"]
            if "ar_balance" in result:
                df["Công nợ phải thu"] = result["ar_balance"]
            if "reserve_required" in result:
                df["Tiền dự trữ yêu cầu"] = result["reserve_required"]

            flow_cols_for_cum = [
                "Tạm ứng CĐT",
                "Thu tiền nghiệm thu",
                "Rút vay thực tế",
                "Chi phí đầu giai đoạn",
                "Chi phí hậu mãi",
                "Lãi vay",
                "Trả gốc",
                "Thuế CIT",
                "Thu hồi cuối kỳ",
                "Vốn công ty bơm vào",
                "Tiền trả về vốn công ty",
                "Dòng tiền vốn công ty",
            ]

            for col in flow_cols_for_cum:
                df[f"Luỹ kế {col}"] = df[col].cumsum()

            horizon_day = int(df["Ngày"].max()) if not df.empty else 0
            month_end_days = list(range(30, horizon_day + 1, 30))
            if horizon_day not in month_end_days:
                month_end_days.append(horizon_day)
            if 0 not in month_end_days:
                month_end_days = [0] + month_end_days

            df_month_end = df[df["Ngày"].isin(month_end_days)].copy()
            if "Tháng quy đổi" in df_month_end.columns:
                df_month_end["Tháng quy đổi"] = df_month_end["Tháng quy đổi"].apply(lambda x: format_vn(x, 2))

            ordered_cols = [
                "Ngày",
                "Tháng quy đổi",
                "Tạm ứng CĐT",
                "Luỹ kế Tạm ứng CĐT",
                "Thu tiền nghiệm thu",
                "Luỹ kế Thu tiền nghiệm thu",
                "Rút vay thực tế",
                "Luỹ kế Rút vay thực tế",
                "Chi phí đầu giai đoạn",
                "Luỹ kế Chi phí đầu giai đoạn",
                "Chi phí hậu mãi",
                "Luỹ kế Chi phí hậu mãi",
                "Lãi vay",
                "Luỹ kế Lãi vay",
                "Trả gốc",
                "Luỹ kế Trả gốc",
                "Thuế CIT",
                "Luỹ kế Thuế CIT",
                "Thu hồi cuối kỳ",
                "Luỹ kế Thu hồi cuối kỳ",
                "Vốn công ty bơm vào",
                "Luỹ kế Vốn công ty bơm vào",
                "Tiền trả về vốn công ty",
                "Luỹ kế Tiền trả về vốn công ty",
                "Dòng tiền vốn công ty",
                "Luỹ kế Dòng tiền vốn công ty",
            ]

            for optional_col in ["Dư nợ cuối ngày", "Tiền cuối ngày", "Công nợ phải thu", "Tiền dự trữ yêu cầu"]:
                if optional_col in df_month_end.columns:
                    ordered_cols.append(optional_col)

            df_month_end = df_month_end[ordered_cols]
            df_display = format_money_series(df_month_end, exclude_cols=["Ngày", "Tháng quy đổi"])
            st.dataframe(df_display, use_container_width=True)

        with st.expander("Giải thích các chỉ số", expanded=False):
            st.write("- **IRR vốn công ty / IRR dự án** được tính trên hệ tháng lẻ: mốc thời gian = ngày/30; hệ thống quét nhiều nghiệm khả dĩ và chọn nghiệm tài chính hợp lý nhất.")
            st.write("- **MIRR vốn công ty / MIRR dự án** dùng cùng trục thời gian tháng lẻ, với finance rate và benchmark reinvestment rate.")
            st.write("- **IRR vốn công ty thực / MIRR vốn công ty thực** = chỉ tiêu annualized sau khi loại trừ lạm phát theo Fisher.")
            st.write("- **Lãi suất NH thực** = lãi suất benchmark danh nghĩa sau khi loại trừ lạm phát theo Fisher.")
            st.write("- **NPV** = Giá trị hiện tại thuần của dòng tiền khi chiết khấu theo lãi suất ngân hàng benchmark năm, quy đổi sang suất tháng hiệu dụng.")
            st.write("- **MIRR thực vs LS NH thực** và **NPV vốn công ty** hiện là 2 trụ chính mới trong bộ đánh giá sơ bộ; IRR chỉ hiển thị tham khảo.")
            st.write("- **Equity Multiple** = Tổng tiền trả về cho vốn công ty / Tổng vốn công ty đã bơm vào.")
            st.write("- **MOIC** = Multiple on Invested Capital. Trong mô hình hiện tại, chỉ số này cùng cơ sở với Equity Multiple nên thường cho cùng kết quả.")
            st.write("- **Net Profit Margin** = Lợi nhuận ròng / Giá trị hợp đồng sau chiết khấu.")
            st.write("- **Thời gian hoàn vốn** = Ngày đầu tiên mà dòng tiền vốn công ty lũy kế quay về mức không âm, sau khi đã từng phải bơm vốn.")
            st.write("- **Billing sau CK** là giá trị nghiệm thu sau chiết khấu; **Cấn trừ tạm ứng** là phần tạm ứng ban đầu được phân bổ vào từng giai đoạn; **Thu tiền thực tế** là số tiền còn thu thêm tại ngày thu tiền của giai đoạn.")
            st.write("- **Chi phí đầu giai đoạn** được tài trợ theo thứ tự: tiền sẵn có/CĐT -> vay của giai đoạn đó -> VCSH.")
            st.write("- **Trả gốc vay** có 2 lựa chọn: trả định kỳ cuối tháng hoặc trả toàn bộ vào cuối tháng cuối cùng chứa kỳ thanh toán cuối.")
            st.write("- **Chiết khấu hợp đồng** làm giảm doanh thu thực nhận.")
            st.write("- **Tạm ứng CĐT ban đầu + tổng thanh toán các giai đoạn** phải bằng đúng 100% giá trị hợp đồng sau chiết khấu.")

    except Exception as e:
        st.error(f"Có lỗi khi xử lý dữ liệu đầu vào hoặc tính toán: {str(e)}")
