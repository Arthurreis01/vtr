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

# Sidebar
st.sidebar.image("logo.png", width=150)
st.sidebar.title("CSupAb - Viaturas")

# Filters
year_min = int(data["YEAR"].min())
year_max = int(data["YEAR"].max())
year_range = st.sidebar.slider(
    "Select Year Range",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max)
)

cam_filter = st.sidebar.multiselect(
    "Filter by CAM",
    options=sorted(data["CAM"].unique()),
    default=None
)

pi_filter = st.sidebar.multiselect(
    "Filter by PI",
    options=sorted(data["PI"].unique()),
    default=None
)

nome_coloquial_filter = st.sidebar.multiselect(
    "Filter by NOME_COLOQUIAL",
    options=sorted(data["NOME_COLOQUIAL"].unique()),
    default=None
)

process_filter = st.sidebar.multiselect(
    "Filter by Process (PROCESSO_AIP)",
    options=sorted(data["PROCESSO_AIP"].unique()),
    default=None
)

# Apply filters
filtered_data = data[(data["YEAR"] >= year_range[0]) & (data["YEAR"] <= year_range[1])]

if cam_filter:
    filtered_data = filtered_data[filtered_data["CAM"].isin(cam_filter)]
if pi_filter:
    filtered_data = filtered_data[filtered_data["PI"].isin(pi_filter)]
if nome_coloquial_filter:
    filtered_data = filtered_data[filtered_data["NOME_COLOQUIAL"].isin(nome_coloquial_filter)]
if process_filter:
    filtered_data = filtered_data[filtered_data["PROCESSO_AIP"].isin(process_filter)]

# Main content
st.markdown("## Dashboard de Análise de EO e PO por Produto e Processo")
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

if not filtered_data.empty:
    # Summarize EO and PO by Product and Process
    product_process_summary = (
        filtered_data.groupby(["PI", "PROCESSO_AIP", "TIPO"])["QTDE"]
        .sum()
        .reset_index()
    )

    # Adjust the spacing to fit all facets
    facet_col_spacing = 0.01  # Reduced spacing between facet columns

    # Chart: EO vs PO by Product and Process
    try:
        product_process_chart = px.bar(
            product_process_summary,
            x="PI",
            y="QTDE",
            color="TIPO",
            barmode="group",
            facet_col="PROCESSO_AIP",
            text="QTDE",
            title="Comparativo EO vs PO por Produto e Processo",
            labels={"QTDE": "Quantity", "PI": "Product (PI)", "PROCESSO_AIP": "Process", "TIPO": "Type"},
            facet_col_spacing=facet_col_spacing,  # Adjusted spacing
            color_discrete_map={"EO": "#E74C3C", "PO": "#3498DB"}
        )
        product_process_chart.update_traces(textposition="outside")
        st.plotly_chart(product_process_chart, use_container_width=True)
    except ValueError as e:
        st.error(f"Failed to create the chart due to spacing constraints: {e}")

    

    # Display detailed table using Ag-Grid
    st.markdown("### Detalhes dos Dados Filtrados")
    gb = GridOptionsBuilder.from_dataframe(product_process_summary)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    gb.configure_default_column(groupable=True, editable=True)
    grid_options = gb.build()

    AgGrid(
        product_process_summary,
        gridOptions=grid_options,
        height=400,
        theme="balham",
        enable_enterprise_modules=False,
    )

    # Add download button for the product-process summary
    st.download_button(
        label="Download Detailed Data as CSV",
        data=product_process_summary.to_csv(index=False).encode("utf-8"),
        file_name="product_process_summary.csv",
        mime="text/csv",
    )
else:
    st.warning("No data available for the selected filters.")
