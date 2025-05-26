from st_aggrid import AgGrid, GridOptionsBuilder
import pandas as pd
import streamlit as st
import plotly.express as px

# Load data with the correct delimiter
try:
    data = pd.read_csv("data-vtr.csv", encoding="latin1", delimiter=";")
    data.columns = data.columns.str.strip()  # Clean column names
except FileNotFoundError:
    st.error("The file 'data-vtr.csv' was not found. Please ensure it is in the correct directory.")
    st.stop()
except Exception as e:
    st.error(f"An error occurred while loading the data: {e}")
    st.stop()

# Ensure necessary columns exist
required_columns = ["DATA", "PI", "CAM", "TIPO", "QTDE", "NOME_COLOQUIAL", "PROCESSO_AIP"]
missing_columns = [col for col in required_columns if col not in data.columns]

if missing_columns:
    st.error(f"The dataset is missing the following required columns: {missing_columns}")
    st.stop()

# Convert 'DATA' to datetime
try:
    data["DATA"] = pd.to_datetime(data["DATA"], format="%d/%m/%Y")
    data["YEAR"] = data["DATA"].dt.year  # Extract year for filtering
except Exception as e:
    st.error(f"An error occurred while parsing 'DATA': {e}")
    st.stop()

# =========================
# SIDEBAR & FILTERS
# =========================
st.sidebar.image("logo.png", width=150)
st.sidebar.title("CSupAb - Viaturas")

# Filter: CAM
cam_filter = st.sidebar.multiselect(
    "Filter by CAM",
    options=sorted(data["CAM"].unique()),
    default=None
)

# Filter: PI
pi_filter = st.sidebar.multiselect(
    "Filter by PI",
    options=sorted(data["PI"].unique()),
    default=None
)

# Filter: NOME_COLOQUIAL
nome_coloquial_filter = st.sidebar.multiselect(
    "Filter by NOME_COLOQUIAL",
    options=sorted(data["NOME_COLOQUIAL"].unique()),
    default=None
)

# Filter: PROCESSO_AIP
process_filter = st.sidebar.multiselect(
    "Filter by Process (PROCESSO_AIP)",
    options=sorted(data["PROCESSO_AIP"].unique()),
    default=None
)

# Filter: YEAR Range
year_min = int(data["YEAR"].min())
year_max = int(data["YEAR"].max())
year_range = st.sidebar.slider(
    "Select Year Range",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max)
)

# Apply filters
filtered_data = data.copy()

if cam_filter:
    filtered_data = filtered_data[filtered_data["CAM"].isin(cam_filter)]
if pi_filter:
    filtered_data = filtered_data[filtered_data["PI"].isin(pi_filter)]
if nome_coloquial_filter:
    filtered_data = filtered_data[filtered_data["NOME_COLOQUIAL"].isin(nome_coloquial_filter)]
if process_filter:
    filtered_data = filtered_data[filtered_data["PROCESSO_AIP"].isin(process_filter)]

filtered_data = filtered_data[
    (filtered_data["YEAR"] >= year_range[0]) & (filtered_data["YEAR"] <= year_range[1])
]

# =========================
# MAIN CONTENT
# =========================
st.markdown("## Dashboard de Análise de EO e PO por Processo")

if not filtered_data.empty:
    # -------------------------------------------------------------------------
    # STEP 1: Summaries
    # -------------------------------------------------------------------------
    total_summary = (
        filtered_data.groupby("TIPO")["QTDE"]
        .sum()
        .reset_index()
    )

    total_eo = total_summary.loc[total_summary["TIPO"] == "EO", "QTDE"].sum()
    total_po = total_summary.loc[total_summary["TIPO"] == "PO", "QTDE"].sum()

    col1, col2 = st.columns(2)
    col1.metric("Total EO", f"{total_eo}")
    col2.metric("Total PO", f"{total_po}")

    # -------------------------------------------------------------------------
    # STEP 2: EO vs PO by PROCESSO_AIP
    # -------------------------------------------------------------------------
    process_summary = (
        filtered_data.groupby(["PROCESSO_AIP", "TIPO"])["QTDE"]
        .sum()
        .reset_index()
    )

    earliest_dates = (
        filtered_data.groupby("PROCESSO_AIP", as_index=False)["DATA"]
        .min()
        .rename(columns={"DATA": "EARLIEST_DATE"})
    )
    process_summary = process_summary.merge(earliest_dates, on="PROCESSO_AIP", how="left")
    process_summary = process_summary.sort_values(by="EARLIEST_DATE", ascending=True)

    try:
        chart_by_process = px.bar(
            process_summary,
            x="PROCESSO_AIP",
            y="QTDE",
            color="TIPO",
            barmode="group",
            text="QTDE",
            title="Comparativo EO vs PO por Processo (Ordem Cronológica)",
            labels={
                "PROCESSO_AIP": "Process",
                "QTDE": "Quantity",
                "TIPO": "Type"
            },
            category_orders={
                "PROCESSO_AIP": list(process_summary["PROCESSO_AIP"].unique())
            },
            color_discrete_map={
                "EO": "#E53D00",   # Dark blue for EO
                "PO": "#F0A202"    # Green for PO
            }
        )
        chart_by_process.update_traces(textposition="outside")
        st.plotly_chart(chart_by_process, use_container_width=True)
    except ValueError as e:
        st.error(f"Failed to create EO vs PO chart: {e}")

    # -------------------------------------------------------------------------
    # STEP 3: New Chart – Compras Agrupadas por CAM
    # -------------------------------------------------------------------------
    cam_summary = (
        filtered_data.groupby("CAM")["QTDE"]
        .sum()
        .reset_index()
    )

    try:
        chart_by_cam = px.bar(
            cam_summary,
            x="CAM",
            y="QTDE",
            text="QTDE",
            title="Compras Agrupadas por CAM",
            labels={"CAM": "CAM", "QTDE": "Quantidade Comprada"}
        )
        chart_by_cam.update_traces(textposition="outside")
        st.plotly_chart(chart_by_cam, use_container_width=True)
    except Exception as e:
        st.error(f"Failed to create Compras por CAM chart: {e}")

    # -------------------------------------------------------------------------
    # STEP 4: Display Table and Download
    # -------------------------------------------------------------------------
    st.markdown("### Detalhes dos Dados Filtrados")

    table_df = process_summary.drop(columns="EARLIEST_DATE")

    gb = GridOptionsBuilder.from_dataframe(table_df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    gb.configure_default_column(groupable=True, editable=True)
    grid_options = gb.build()

    AgGrid(
        table_df,
        gridOptions=grid_options,
        height=400,
        theme="balham",
        enable_enterprise_modules=False,
    )

    st.download_button(
        label="Download Detailed Data as CSV",
        data=table_df.to_csv(index=False).encode("utf-8"),
        file_name="process_summary.csv",
        mime="text/csv",
    )

else:
    st.warning("No data available for the selected filters.")
