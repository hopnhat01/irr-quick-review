import streamlit as st
import pandas as pd

from engine import build_model

# ===== MẬT KHẨU =====
PASSWORD = "123456"


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Truy cập hệ thống")

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


check_password()

# ===== APP CHÍNH =====

st.title("Công cụ ước tính hiệu quả deal")

st.subheader("1. Thông tin cơ bản")

deal_value = st.number_input(
    "Giá trị hợp đồng (VND)",
    value=10000000000,
    step=1000000,
    format="%d",
    help="Tổng giá trị hợp đồng với khách",
)
st.caption("Hiển thị: " + format_vn(deal_value, 0) + " đ")

cost_pct = st.number_input(
    "Tỷ lệ giá vốn (% tính trên giá trị hợp đồng)",
    value=70.0,
)
st.caption("Hiển thị: " + format_vn(cost_pct, 2) + " %")

project_months = st.number_input(
    "Thời gian thực hiện (tháng)",
    value=6,
    step=1,
    format="%d",
)

dso_days = st.number_input(
    "Số ngày công nợ thỏa thuận (DSO)",
    value=30,
    step=1,
    format="%d",
)

tax_rate = st.number_input(
    "Thuế suất thuế thu nhập doanh nghiệp (% thuế suất)",
    value=20.0,
)
st.caption("Hiển thị: " + format_vn(tax_rate, 2) + " %")

salvage_pct = st.number_input(
    "Giá trị thu hồi cuối kỳ (% giá trị hợp đồng)",
    value=0.0,
)
st.caption("Hiển thị: " + format_vn(salvage_pct, 2) + " %")

st.subheader("2. Vốn và vay")

debt_pct = st.number_input(
    "Tỷ lệ vốn vay (% chi phí giá vốn gốc)",
    value=50.0,
)
st.caption("Hiển thị: " + format_vn(debt_pct, 2) + " %")

interest_rate = st.number_input(
    "Lãi suất vay/năm (% lãi suất)",
    value=12.0,
)
st.caption("Hiển thị: " + format_vn(interest_rate, 2) + " %")

st.subheader("3. Thanh toán")

payment_type = st.selectbox(
    "Cách khách thanh toán",
    ["Trả trước", "Theo tiến độ", "Trả sau"],
)

upfront_pct = 0.0
progress_pct = 0.0

if payment_type == "Trả trước":
    upfront_pct = st.number_input(
        "Tỷ lệ trả trước (% giá trị hợp đồng)",
        value=30.0,
    )
    st.caption("Hiển thị: " + format_vn(upfront_pct, 2) + " %")

if payment_type == "Theo tiến độ":
    progress_pct = st.number_input(
        "Tỷ lệ thu theo tiến độ (%)",
        value=50.0,
    )
    st.caption("Hiển thị: " + format_vn(progress_pct, 2) + " %")

st.subheader("4. Chi phí")

cost_timing = st.selectbox(
    "Thời điểm chi phí",
    ["Trả đều", "Trả đầu kỳ", "Trả cuối kỳ"],
)

run_button = st.button("Tính kết quả")

if run_button:
    if cost_pct > 100:
        st.error("Tỷ lệ giá vốn không thể lớn hơn 100%.")
        st.stop()

    if debt_pct > 100:
        st.error("Tỷ lệ vốn vay không thể lớn hơn 100%.")
        st.stop()

    if upfront_pct > 100:
        st.error("Tỷ lệ trả trước không thể lớn hơn 100%.")
        st.stop()

    if progress_pct > 100:
        st.error("Tỷ lệ thu theo tiến độ không thể lớn hơn 100%.")
        st.stop()

    inputs = {
        "deal_value": deal_value,
        "cost_pct": cost_pct,
        "project_months": project_months,
        "dso_days": dso_days,
        "debt_pct": debt_pct,
        "interest_rate": interest_rate,
        "payment_type": payment_type,
        "upfront_pct": upfront_pct,
        "progress_pct": progress_pct,
        "cost_timing": cost_timing,
        "tax_rate": tax_rate,
        "salvage_pct": salvage_pct,
    }

    result = build_model(inputs)

    with st.expander("Giải thích các chỉ số (bấm để xem)"):
        st.write("**Tỷ suất sinh lời trên vốn (IRR)**: mức sinh lời ước tính trên phần vốn công ty thực sự phải bỏ ra.")
        st.write("**Thời gian hoàn vốn**: thời điểm dòng tiền tích lũy quay về từ âm sang không âm hoặc dương.")
        st.write("**Mức vốn bị giam lớn nhất**: mức âm lớn nhất của dòng tiền tích lũy trong suốt deal.")
        st.write("**DSO**: số ngày dự kiến phải chờ để thu tiền từ khách.")

    st.subheader("Kết quả")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Tỷ suất sinh lời trên vốn",
        format_vn(result["irr_annual"], 2) + " %" if result["irr_annual"] is not None else "Không tính được",
    )

    col2.metric(
        "Thời gian hoàn vốn",
        f"{result['payback_month']} tháng" if result["payback_month"] is not None else "Chưa hoàn vốn",
    )

    col3.metric(
        "Mức vốn bị giam lớn nhất",
        format_vn(result["peak_cash_out"], 0) + " đ",
    )

    st.metric(
        "Tiền ròng tại thời điểm bắt đầu",
        format_vn(result["net_cash_t0"], 0) + " đ",
    )

    if result["decision"] == "GO":
        st.success("Đánh giá sơ bộ: GO - Nên làm")
    elif result["decision"] == "REVIEW":
        st.warning("Đánh giá sơ bộ: REVIEW - Cần xem lại")
    else:
        st.error("Đánh giá sơ bộ: NO GO - Không nên làm")

    st.write("**Diễn giải nhanh**")
    st.write(
        f"Vốn công ty phải bỏ ra ban đầu ước tính khoảng {format_vn(result['equity'], 0)} đ. "
        f"Vốn vay thực tế sau khi trừ phần khách trả trước là khoảng {format_vn(result['actual_debt'], 0)} đ."
    )

    st.subheader("Bảng dòng tiền")

    df = pd.DataFrame(
        {
            "Tháng": result["timeline"],
            "Tiền thu": result["revenue"],
            "Chi phí": result["cost"],
            "Lãi vay": result["interest"],
            "Trả gốc": result["principal"],
            "Thuế": result["tax"],
            "Thu hồi": result["salvage"],
            "Vốn bỏ ra": result["equity_outflow"],
            "Dòng tiền ròng": result["net_cf"],
            "Dòng tiền tích lũy": result["cum_cf"],
        }
    )

    df_display = df.copy()
    for col in [
        "Tiền thu",
        "Chi phí",
        "Lãi vay",
        "Trả gốc",
        "Thuế",
        "Thu hồi",
        "Vốn bỏ ra",
        "Dòng tiền ròng",
        "Dòng tiền tích lũy",
    ]:
        df_display[col] = df_display[col].apply(lambda x: format_vn(x, 0))

    st.dataframe(df_display, use_container_width=True)

    st.subheader("Biểu đồ dòng tiền tích lũy")
    chart_df = df.set_index("Tháng")[["Dòng tiền tích lũy"]]
    st.line_chart(chart_df)
