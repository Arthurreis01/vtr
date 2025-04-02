from st_aggrid import AgGrid, GridOptionsBuilder
import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# =========================
# DATA LOADING
# =========================
st.set_page_config(layout='wide', initial_sidebar_state='expanded')
try:
    # Load data with the correct delimiter
    data = pd.read_csv("data-vtr.csv", encoding="latin1", delimiter=";")
    data.columns = data.columns.str.strip()  # Clean column names
except FileNotFoundError:
    st.error("The file 'data-vtr.csv' was not found. Please ensure it is in the correct directory.")
    st.stop()
except Exception as e:
    st.error(f"An error occurred while loading the data: {e}")
    st.stop()

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

# Filter: YEAR RANGE (last item)
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
    # STEP 2: CHART BY PROCESS (EO vs PO) - GROUPED
    # -------------------------------------------------------------------------
    process_summary = (
        filtered_data.groupby(["PROCESSO_AIP", "TIPO"])["QTDE"]
        .sum()
        .reset_index()
    )

    # Sort by earliest date
    earliest_dates = (
        filtered_data.groupby("PROCESSO_AIP", as_index=False)["DATA"]
        .min()
        .rename(columns={"DATA": "EARLIEST_DATE"})
    )
    process_summary = process_summary.merge(earliest_dates, on="PROCESSO_AIP", how="left")
    process_summary.sort_values(by="EARLIEST_DATE", inplace=True)

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
                "EO": "#1F77B4",   # Dark blue for EO
                "PO": "#2CA02C"    # Green for PO
            }
        )
        chart_by_process.update_traces(textposition="outside")
        st.plotly_chart(chart_by_process, use_container_width=True)
    except ValueError as e:
        st.error(f"Failed to create Chart #1: {e}")

    # -------------------------------------------------------------------------
    # STEP 3: MACHINE LEARNING (Simple Example)
    # -------------------------------------------------------------------------
    st.markdown("## Previsão de Próximo EO (Exemplo Simplificado)")

    # 1) Prepare data: pivot so we have columns EO, PO
    #    We'll do a basic approach: pivot TIPO => columns.
    pivot_df = (
        filtered_data.groupby(["PROCESSO_AIP", "TIPO"], as_index=False)["QTDE"]
        .sum()
        .pivot(index="PROCESSO_AIP", columns="TIPO", values="QTDE")
        .fillna(0)
        .reset_index()
    )
    # pivot_df columns: [PROCESSO_AIP, EO, PO]

    # 2) Merge earliest date for sorting & optionally the # of unique items
    pivot_df = pivot_df.merge(earliest_dates, on="PROCESSO_AIP", how="left")
    pivot_df.sort_values("EARLIEST_DATE", inplace=True)

    # 3) Create features: e.g., use PO as predictor, predict EO
    #    This is extremely naive: next process's EO from current PO
    if "PO" not in pivot_df.columns:
        pivot_df["PO"] = 0  # If no PO found

    # We'll create a shift as if we want to predict next EO from current PO
    pivot_df["EO_next"] = pivot_df["EO"].shift(-1)  # the 'future' EO
    pivot_df.dropna(subset=["EO_next"], inplace=True)  # remove last row

    # Features = current PO, Target = next EO
    X = pivot_df[["PO"]]
    y = pivot_df["EO_next"]

    if len(X) > 2:
        from sklearn.ensemble import RandomForestRegressor
        # Simple train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, shuffle=False, random_state=42)
        model = RandomForestRegressor(random_state=42)
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = mean_squared_error(y_test, y_pred, squared=False)

        st.write(f"MAE: {mae:.2f}, RMSE: {rmse:.2f}")

        # We'll do a final naive prediction: if user wants next EO for the last row's PO
        last_po = pivot_df["PO"].iloc[-1]
        next_eo_pred = model.predict([[last_po]])[0]
        st.write(f"**Previsão de Próximo EO (Exemplo) com base no PO={last_po}:** {next_eo_pred:.2f}")

    else:
        st.warning("Not enough data to run the ML model (need more rows).")

    # -------------------------------------------------------------------------
    # STEP 4: Display Table & Download
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
