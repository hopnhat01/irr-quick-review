import streamlit as st
import pandas as pd

from engine import build_model


PASSWORD = "000"


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
    if number is None:
        return "-"
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_optional_int(value, field_name):
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(text)
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
        if col not in exclude_cols:
            df_display[col] = df_display[col].apply(
                lambda x: format_vn(x, 0) if isinstance(x, (int, float)) else x
            )
    return df_display


check_password()

st.title("Công cụ ước tính hiệu quả deal")

with st.expander("Giải thích nhanh cách nhập liệu", expanded=False):
    st.write("1) Tạm ứng CĐT ban đầu được nhập theo % giá trị hợp đồng.")
    st.write("2) Giai đoạn nghiệm thu tối đa 5 giai đoạn, có thể để trống các giai đoạn cuối.")
    st.write("3) Mỗi giai đoạn cần nhập thời lượng thi công và tỷ lệ thanh toán theo giá trị hợp đồng.")
    st.write("4) Giải ngân vay tối đa 4 đợt, đi theo các giai đoạn 1 đến 4 và nhập theo % giá vốn.")
    st.write("5) Thuế CIT là thuế thu nhập doanh nghiệp.")
    st.write("6) Số ngày công nợ là số ngày chậm thanh toán trung bình sau mỗi lần nghiệm thu.")


# =========================
# 1. THÔNG TIN CƠ BẢN
# =========================
st.subheader("1. Thông tin cơ bản")

deal_value = st.number_input(
    "Giá trị hợp đồng (VND)",
    min_value=0,
    value=10_000_000_000,
    step=1_000_000,
    format="%d",
    help="Tổng giá trị hợp đồng với khách hàng.",
)
st.caption("Hiển thị: " + format_vn(deal_value, 0) + " đ")

cost_pct = st.number_input(
    "Tỷ lệ giá vốn (% theo giá trị hợp đồng)",
    min_value=0.0,
    max_value=100.0,
    value=70.0,
    step=0.1,
)
st.caption("Hiển thị: " + format_vn(cost_pct, 2) + " %")

salvage_pct = st.number_input(
    "Giá trị thu hồi cuối kỳ (% theo giá trị hợp đồng)",
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

total_cost_preview = deal_value * cost_pct / 100.0
salvage_preview = deal_value * salvage_pct / 100.0

col_basic_1, col_basic_2 = st.columns(2)
col_basic_1.metric("Tổng giá vốn ước tính", format_vn(total_cost_preview, 0) + " đ")
col_basic_2.metric("Giá trị thu hồi cuối kỳ", format_vn(salvage_preview, 0) + " đ")


# =========================
# 2. NGUỒN VỐN
# =========================
st.subheader("2. Nguồn vốn")

owner_advance_pct = st.number_input(
    "Tỷ lệ tạm ứng chủ đầu tư ban đầu (% theo giá trị hợp đồng)",
    min_value=0.0,
    max_value=100.0,
    value=10.0,
    step=0.1,
    help="Đây là khoản tạm ứng ban đầu của chủ đầu tư, tính theo % giá trị hợp đồng.",
)
st.caption("Hiển thị: " + format_vn(owner_advance_pct, 2) + " %")

interest_rate = st.number_input(
    "Lãi suất vay năm (%)",
    min_value=0.0,
    max_value=100.0,
    value=12.0,
    step=0.1,
)
st.caption("Hiển thị: " + format_vn(interest_rate, 2) + " %")

owner_advance_amount_preview = deal_value * owner_advance_pct / 100.0
st.metric("Giá trị tạm ứng CĐT ban đầu", format_vn(owner_advance_amount_preview, 0) + " đ")


# =========================
# 3. CÁC GIAI ĐOẠN NGHIỆM THU
# =========================
st.subheader("3. Các giai đoạn nghiệm thu")

st.caption(
    "Nhập tối đa 5 giai đoạn. Có thể để trống các giai đoạn cuối. "
    "Mỗi giai đoạn gồm thời lượng thi công (tháng) và tỷ lệ thanh toán (% theo giá trị hợp đồng)."
)

default_stage_names = [
    "Giai đoạn 1",
    "Giai đoạn 2",
    "Giai đoạn 3",
    "Giai đoạn 4",
    "Giai đoạn 5",
]

default_stage_duration = ["2", "3", "2", "", ""]
default_stage_payment = ["30", "40", "30", "", ""]

stage_names = []
stage_duration_raw = []
stage_payment_raw = []

header_cols = st.columns([2.2, 1.2, 1.4])
header_cols[0].markdown("**Tên giai đoạn**")
header_cols[1].markdown("**Thời gian (tháng)**")
header_cols[2].markdown("**Thanh toán (% HĐ)**")

for i in range(5):
    cols = st.columns([2.2, 1.2, 1.4])

    with cols[0]:
        stage_name = st.text_input(
            f"Tên giai đoạn {i+1}",
            value=default_stage_names[i],
            key=f"stage_name_{i+1}",
            label_visibility="collapsed",
        )

    with cols[1]:
        duration_text = st.text_input(
            f"Thời gian giai đoạn {i+1}",
            value=default_stage_duration[i],
            key=f"stage_duration_{i+1}",
            help="Có thể để trống nếu không dùng giai đoạn này.",
            label_visibility="collapsed",
            placeholder="Để trống nếu không dùng",
        )

    with cols[2]:
        payment_text = st.text_input(
            f"Thanh toán giai đoạn {i+1}",
            value=default_stage_payment[i],
            key=f"stage_payment_{i+1}",
            help="Tỷ lệ thanh toán của khách ở giai đoạn này (% theo giá trị hợp đồng).",
            label_visibility="collapsed",
            placeholder="Để trống nếu không dùng",
        )

    stage_names.append(stage_name)
    stage_duration_raw.append(duration_text)
    stage_payment_raw.append(payment_text)


# =========================
# 4. GIẢI NGÂN VAY THEO GIAI ĐOẠN
# =========================
st.subheader("4. Giải ngân vay theo giai đoạn")

st.caption(
    "Tối đa 4 đợt giải ngân vay, tương ứng với các giai đoạn 1 đến 4. "
    "Các tỷ lệ này nhập theo % giá vốn."
)

default_loan_draw_raw = ["20", "20", "", ""]
loan_draw_raw = []

loan_cols = st.columns(4)
for i in range(4):
    with loan_cols[i]:
        draw_text = st.text_input(
            f"Vay GĐ{i+1} (% giá vốn)",
            value=default_loan_draw_raw[i],
            key=f"loan_draw_{i+1}",
            placeholder="Để trống nếu không dùng",
        )
        loan_draw_raw.append(draw_text)


# =========================
# 5. HẬU MÃI / BẢO HÀNH / BẢO HIỂM
# =========================
st.subheader("5. Hậu mãi / bảo hành / bảo hiểm")

after_sales_pct = st.number_input(
    "Chi phí bảo hành / bảo hiểm hậu mãi (% theo giá trị hợp đồng)",
    min_value=0.0,
    max_value=100.0,
    value=5.0,
    step=0.1,
)
st.caption("Hiển thị: " + format_vn(after_sales_pct, 2) + " %")

warranty_months = st.number_input(
    "Thời hạn bảo hành / hậu mãi (tháng)",
    min_value=0,
    value=12,
    step=1,
    format="%d",
)
st.caption("Hiển thị: " + format_vn(warranty_months, 0) + " tháng")

after_sales_amount_preview = deal_value * after_sales_pct / 100.0
st.metric("Tổng chi phí hậu mãi ước tính", format_vn(after_sales_amount_preview, 0) + " đ")


run_button = st.button("Tính kết quả")


if run_button:
    try:
        errors = []

        # -------------------------
        # Parse stages
        # -------------------------
        stages = []
        blank_stage_started = False

        for i in range(5):
            stage_no = i + 1
            stage_name = stage_names[i].strip() if stage_names[i].strip() else f"Giai đoạn {stage_no}"

            duration_months = parse_optional_int(
                stage_duration_raw[i],
                f"Thời gian giai đoạn {stage_no}",
            )
            payment_pct = parse_optional_float(
                stage_payment_raw[i],
                f"Thanh toán giai đoạn {stage_no}",
            )

            if duration_months is None and payment_pct is None:
                blank_stage_started = True
                continue

            if blank_stage_started:
                errors.append("Các giai đoạn nghiệm thu phải được nhập liên tục từ giai đoạn 1, không được bỏ trống ở giữa.")

            if duration_months is None and payment_pct is not None:
                errors.append(f"Giai đoạn {stage_no} đang có tỷ lệ thanh toán nhưng chưa nhập thời gian.")
                continue

            if duration_months is not None and payment_pct is None:
                errors.append(f"Giai đoạn {stage_no} đang có thời gian nhưng chưa nhập tỷ lệ thanh toán.")
                continue

            if duration_months is not None and duration_months <= 0:
                errors.append(f"Thời gian của giai đoạn {stage_no} phải lớn hơn 0 tháng.")

            if payment_pct is not None and payment_pct <= 0:
                errors.append(f"Tỷ lệ thanh toán của giai đoạn {stage_no} phải lớn hơn 0%.")

            if payment_pct is not None and payment_pct > 100:
                errors.append(f"Tỷ lệ thanh toán của giai đoạn {stage_no} không thể lớn hơn 100%.")

            stages.append(
                {
                    "stage_no": stage_no,
                    "name": stage_name,
                    "duration_months": duration_months,
                    "payment_pct": payment_pct,
                }
            )

        if len(stages) == 0:
            errors.append("Phải nhập ít nhất 1 giai đoạn nghiệm thu.")

        total_project_months = sum(stage["duration_months"] for stage in stages) if stages else 0
        total_payment_pct = sum(stage["payment_pct"] for stage in stages) if stages else 0.0

        if stages and abs(total_payment_pct - 100.0) > 1e-6:
            errors.append("Tổng tỷ lệ thanh toán của các giai đoạn nghiệm thu phải bằng đúng 100% giá trị hợp đồng.")

        # -------------------------
        # Parse loan draw schedule
        # -------------------------
        debt_draw_schedule = []
        blank_loan_started = False

        for i in range(4):
            stage_no = i + 1
            draw_pct_cost = parse_optional_float(
                loan_draw_raw[i],
                f"Giải ngân vay giai đoạn {stage_no}",
            )

            if draw_pct_cost is None:
                blank_loan_started = True
                continue

            if blank_loan_started:
                errors.append("Các đợt giải ngân vay phải nhập liên tục từ giai đoạn 1.")

            if draw_pct_cost < 0:
                errors.append(f"Giải ngân vay giai đoạn {stage_no} không được âm.")

            if draw_pct_cost > 100:
                errors.append(f"Giải ngân vay giai đoạn {stage_no} không thể lớn hơn 100% giá vốn.")

            if stage_no > len(stages):
                errors.append(f"Không thể nhập giải ngân vay ở giai đoạn {stage_no} khi dự án chỉ có {len(stages)} giai đoạn nghiệm thu.")

            debt_draw_schedule.append(
                {
                    "stage_no": stage_no,
                    "draw_pct_cost": draw_pct_cost,
                }
            )

        total_debt_draw_pct = sum(item["draw_pct_cost"] for item in debt_draw_schedule) if debt_draw_schedule else 0.0

        if total_debt_draw_pct > 100:
            errors.append("Tổng tỷ lệ giải ngân vay không thể lớn hơn 100% giá vốn.")

        # -------------------------
        # Basic validations
        # -------------------------
        if cost_pct > 100:
            errors.append("Tỷ lệ giá vốn không thể lớn hơn 100%.")

        if salvage_pct > 100:
            errors.append("Giá trị thu hồi cuối kỳ không thể lớn hơn 100% giá trị hợp đồng.")

        if tax_rate > 100:
            errors.append("Thuế CIT không thể lớn hơn 100%.")

        if owner_advance_pct > 100:
            errors.append("Tỷ lệ tạm ứng chủ đầu tư ban đầu không thể lớn hơn 100% giá trị hợp đồng.")

        if after_sales_pct > 100:
            errors.append("Chi phí bảo hành / bảo hiểm hậu mãi không thể lớn hơn 100% giá trị hợp đồng.")

        if warranty_months < 0:
            errors.append("Thời hạn bảo hành / hậu mãi không được âm.")

        if errors:
            for err in errors:
                st.error(err)
            st.stop()

        inputs = {
            "deal_value": float(deal_value),
            "cost_pct": float(cost_pct),
            "salvage_pct": float(salvage_pct),
            "tax_rate": float(tax_rate),              # CIT
            "avg_dso_days": int(avg_dso_days),

            "owner_advance_pct": float(owner_advance_pct),   # % theo giá trị hợp đồng
            "interest_rate": float(interest_rate),

            "stages": stages,                                  # thời gian + payment %
            "debt_draw_schedule": debt_draw_schedule,          # tối đa 4 đợt, % theo giá vốn

            "after_sales_pct": float(after_sales_pct),        # % theo giá trị hợp đồng
            "warranty_months": int(warranty_months),

            "total_project_months": int(total_project_months),
        }

        with st.expander("Dữ liệu đầu vào đã chuẩn hóa"):
            st.json(inputs)

        result = build_model(inputs)

        st.subheader("Kết quả")

        col1, col2, col3 = st.columns(3)

        equity_irr = result.get("equity_irr_annual", result.get("irr_annual"))
        payback_month = result.get("payback_month")
        peak_equity = result.get("peak_equity_at_risk", result.get("peak_cash_out"))

        col1.metric(
            "IRR vốn chủ",
            format_vn(equity_irr, 2) + " %" if equity_irr is not None else "Không tính được",
        )

        col2.metric(
            "Thời gian hoàn vốn",
            f"{payback_month} tháng" if payback_month is not None else "Chưa hoàn vốn",
        )

        col3.metric(
            "Mức vốn bị giam lớn nhất",
            format_vn(peak_equity, 0) + " đ" if peak_equity is not None else "-",
        )

        col4, col5, col6 = st.columns(3)

        project_irr = result.get("project_irr_annual")
        peak_debt = result.get("peak_debt")
        total_cost = result.get("total_cost")

        col4.metric(
            "IRR dự án",
            format_vn(project_irr, 2) + " %" if project_irr is not None else "Không tính được",
        )

        col5.metric(
            "Dư nợ vay lớn nhất",
            format_vn(peak_debt, 0) + " đ" if peak_debt is not None else "-",
        )

        col6.metric(
            "Tổng giá vốn",
            format_vn(total_cost, 0) + " đ" if total_cost is not None else "-",
        )

        decision = result.get("decision")
        if decision == "GO":
            st.success("Đánh giá sơ bộ: GO - Nên làm")
        elif decision == "REVIEW":
            st.warning("Đánh giá sơ bộ: REVIEW - Cần xem lại")
        elif decision == "NO GO":
            st.error("Đánh giá sơ bộ: NO GO - Không nên làm")

        if result.get("stage_plan"):
            st.subheader("Kế hoạch các giai đoạn")
            stage_df = pd.DataFrame(result["stage_plan"])
            stage_df_display = stage_df.copy()

            money_cols = [
                "gross_billing_value",
                "advance_offset",
                "net_collection_value",
                "stage_cost",
            ]
            for col in money_cols:
                if col in stage_df_display.columns:
                    stage_df_display[col] = stage_df_display[col].apply(lambda x: format_vn(x, 0))

            st.dataframe(stage_df_display, use_container_width=True)

        if result.get("timeline") and result.get("equity_cf"):
            st.subheader("Biểu đồ dòng tiền vốn chủ")
            chart_df = pd.DataFrame(
                {
                    "Tháng": result["timeline"],
                    "Dòng tiền vốn chủ": result["equity_cf"],
                }
            ).set_index("Tháng")
            st.line_chart(chart_df)

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
                    "Tháng": result["timeline"],
                    "Tạm ứng CĐT": result["customer_advance"],
                    "Thu tiền nghiệm thu": result["collections"],
                    "Giải ngân vay": result["debt_draw"],
                    "Chi phí đầu giai đoạn": result["cost"],
                    "Chi phí hậu mãi": result["after_sales"],
                    "Lãi vay": result["interest"],
                    "Trả gốc": result["principal"],
                    "Thuế CIT": result["tax"],
                    "Thu hồi cuối kỳ": result["salvage"],
                    "Vốn chủ bơm vào": result["equity_in"],
                    "Tiền trả về vốn chủ": result["equity_out"],
                    "Dòng tiền vốn chủ": result["equity_cf"],
                }
            )

            if "closing_cash" in result:
                df["Tiền cuối kỳ"] = result["closing_cash"]

            df_display = format_money_series(df, exclude_cols=["Tháng"])
            st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        st.error(f"Có lỗi khi xử lý dữ liệu đầu vào hoặc tính toán: {str(e)}")
