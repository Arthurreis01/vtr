from st_aggrid import AgGrid, GridOptionsBuilder
import pandas as pd
import streamlit as st
import plotly.express as px

# Load data with the correct delimiter
try:
    data = pd.read_csv("data-vtr.csv", encoding="latin1", delimiter=";")
    # Clean column names
    data.columns = data.columns.str.strip()
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

# Sidebar
st.sidebar.image("logo.png", width=150)  # Reduce the size of the logo
st.sidebar.title("CSupAb - Viaturas")

# Prepare sorted options for filters:
# 1) CAM: put B001 at the top (if it exists), then keep others in ascending order
cam_unique = sorted(data["CAM"].unique())
if "B001" in cam_unique:
    cam_unique.remove("B001")
    cam_unique.insert(0, "B001")

# 2) PI: from the lowest to highest
pi_unique = sorted(data["PI"].unique())

# 3) NOME_COLOQUIAL: alphabetical order
nome_coloquial_unique = sorted(data["NOME_COLOQUIAL"].unique())

# Filters
pi_filter = st.sidebar.multiselect(
    "Filter by PI",
    options=pi_unique,
    default=None
)

cam_filter = st.sidebar.multiselect(
    "Filter by CAM",
    options=cam_unique,
    default=None
)

nome_coloquial_filter = st.sidebar.multiselect(
    "Filter by NOME_COLOQUIAL",
    options=nome_coloquial_unique,
    default=None
)

# Year Range Filter
year_min = int(data["YEAR"].min())
year_max = int(data["YEAR"].max())
year_range = st.sidebar.slider(
    "Select Year Range",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max)
)

# Apply filters
filtered_data = data[(data["YEAR"] >= year_range[0]) & (data["YEAR"] <= year_range[1])]

if pi_filter:
    filtered_data = filtered_data[filtered_data["PI"].isin(pi_filter)]
if cam_filter:
    filtered_data = filtered_data[filtered_data["CAM"].isin(cam_filter)]
if nome_coloquial_filter:
    filtered_data = filtered_data[filtered_data["NOME_COLOQUIAL"].isin(nome_coloquial_filter)]

# Main content
st.markdown("## Dashboard de Análise de EO e PO")

if not filtered_data.empty:
    # Total EO and PO Summaries
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

    # 1) NEW CHART: Simplified comparison EO vs PO by YEAR
    yearly_eo_po = (
        filtered_data.groupby(["YEAR", "TIPO"])["QTDE"]
        .sum()
        .reset_index()
    )

    comp_bar_chart = px.bar(
        yearly_eo_po,
        x="YEAR",
        y="QTDE",
        color="TIPO",
        barmode="group",
        text="QTDE",
        title="Comparativo EO vs PO por Ano",
        labels={"QTDE": "Total Quantity", "YEAR": "Year", "TIPO": "Type"},
        color_discrete_map={
            "EO": "#E74C3C",  # Bright red
            "PO": "#3498DB",  # Bright blue
        }
    )
    comp_bar_chart.update_traces(textposition="outside")
    st.plotly_chart(comp_bar_chart, use_container_width=True)

    # 2) EXISTING CHART: Anual EO x PO 2020 à 2024 (Stacked por CAM)
    yearly_cam_data = (
        filtered_data.groupby(["YEAR", "TIPO", "CAM"])["QTDE"]
        .sum()
        .reset_index()
    )

    yearly_bar_chart = px.bar(
        yearly_cam_data,
        x="YEAR",
        y="QTDE",
        color="CAM",
        barmode="stack",
        facet_col="TIPO",
        text="QTDE",
        title="Anual EO x PO 2020 à 2024 (Detalhado por CAM)",
        labels={"QTDE": "Total Quantity", "YEAR": "Year", "CAM": "CAM"},
    )
    yearly_bar_chart.update_traces(textposition="outside")
    st.plotly_chart(yearly_bar_chart, use_container_width=True)

    # Add drill-down by year and process
    st.markdown("### Análise detalhada: Processos de Obtenção por ano")
    selected_year = st.selectbox("Selecione um ano para análise detalhada do processo", yearly_cam_data["YEAR"].unique())

    # Filter data for the selected year
    year_filtered_data = filtered_data[filtered_data["YEAR"] == selected_year]

    process_summary = (
        year_filtered_data.groupby(["PROCESSO_AIP", "TIPO"])["QTDE"]
        .sum()
        .reset_index()
    )

    process_bar_chart = px.bar(
        process_summary,
        x="PROCESSO_AIP",
        y="QTDE",
        color="TIPO",
        barmode="group",
        title=f"Process-Level EO and PO for {selected_year}",
        labels={"QTDE": "Quantity", "PROCESSO_AIP": "Process", "TIPO": "Type"},
        color_discrete_map={
            "EO": "#E74C3C",
            "PO": "#3498DB",
        }
    )
    st.plotly_chart(process_bar_chart, use_container_width=True)

    # Display detailed table using Ag-Grid
    st.markdown(f"### Dados detalhados de {selected_year}")
    gb = GridOptionsBuilder.from_dataframe(year_filtered_data)
    gb.configure_pagination(paginationAutoPageSize=True)  # Enable pagination
    gb.configure_side_bar()  # Enable sidebar filters
    gb.configure_default_column(groupable=True, editable=True)  # Allow grouping and editing
    grid_options = gb.build()

    AgGrid(
        year_filtered_data,
        gridOptions=grid_options,
        height=400,
        theme="balham",
        enable_enterprise_modules=False,
    )

    # Add download button for the filtered data
    st.download_button(
        label="Download Detailed Data as CSV",
        data=year_filtered_data.to_csv(index=False).encode("utf-8"),
        file_name=f"detailed_data_{selected_year}.csv",
        mime="text/csv",
    )
else:
    st.warning("No data available for the selected filters.")
