from st_aggrid import AgGrid, GridOptionsBuilder
import pandas as pd
import streamlit as st
import plotly.express as px

# -------------------------
# CARREGAMENTO E TRATAMENTO
# -------------------------
try:
    data = pd.read_csv("data-vtr.csv", encoding="latin1", delimiter=";")
    data.columns = data.columns.str.strip()
except FileNotFoundError:
    st.error("O arquivo 'data-vtr.csv' não foi encontrado.")
    st.stop()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

required_columns = ["DATA", "PI", "CAM", "TIPO", "QTDE", "NOME_COLOQUIAL", "PROCESSO_AIP"]
missing = [c for c in required_columns if c not in data.columns]
if missing:
    st.error(f"Colunas faltando: {missing}")
    st.stop()

try:
    data["DATA"] = pd.to_datetime(data["DATA"], format="%d/%m/%Y")
    data["YEAR"] = data["DATA"].dt.year
except Exception as e:
    st.error(f"Erro ao converter DATA: {e}")
    st.stop()

# -------------------------
# SIDEBAR & FILTROS
# -------------------------
st.sidebar.image("logo.png", width=150)
st.sidebar.title("CSupAb - Viaturas")

cam_filter = st.sidebar.multiselect("Filter by CAM", sorted(data["CAM"].unique()))
pi_filter = st.sidebar.multiselect("Filter by PI", sorted(data["PI"].unique()))
nome_filter = st.sidebar.multiselect("Filter by NOME_COLOQUIAL", sorted(data["NOME_COLOQUIAL"].unique()))
proc_filter = st.sidebar.multiselect("Filter by Process (PROCESSO_AIP)", sorted(data["PROCESSO_AIP"].unique()))
year_min, year_max = int(data["YEAR"].min()), int(data["YEAR"].max())
year_range = st.sidebar.slider("Select Year Range", year_min, year_max, (year_min, year_max))

f = data.copy()
if cam_filter:       f = f[f["CAM"].isin(cam_filter)]
if pi_filter:        f = f[f["PI"].isin(pi_filter)]
if nome_filter:      f = f[f["NOME_COLOQUIAL"].isin(nome_filter)]
if proc_filter:      f = f[f["PROCESSO_AIP"].isin(proc_filter)]
f = f[(f["YEAR"] >= year_range[0]) & (f["YEAR"] <= year_range[1])]

# -------------------------
# TÍTULO
# -------------------------
st.markdown("## Dashboard de Análise de EO e PO por Processo")

if f.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# -------------------------
# STEP 1: Métricas Totais
# -------------------------
tot = f.groupby("TIPO")["QTDE"].sum().reset_index()
eo_total = int(tot.loc[tot["TIPO"]=="EO","QTDE"].sum())
po_total = int(tot.loc[tot["TIPO"]=="PO","QTDE"].sum())
c1, c2 = st.columns(2)
c1.metric("Total EO", eo_total)
c2.metric("Total PO", po_total)

# -------------------------
# STEP 2: EO vs PO por PROCESSO (cronológico)
# -------------------------
proc_tipo = f.groupby(["PROCESSO_AIP","TIPO"])["QTDE"].sum().reset_index()
first_dates = (
    f.groupby("PROCESSO_AIP", as_index=False)["DATA"]
     .min()
     .rename(columns={"DATA":"EARLIEST_DATE"})
)
proc_tipo = proc_tipo.merge(first_dates, on="PROCESSO_AIP")
proc_tipo = proc_tipo.sort_values("EARLIEST_DATE")
order_proc = proc_tipo["PROCESSO_AIP"].drop_duplicates().tolist()

chart1 = px.bar(
    proc_tipo,
    x="PROCESSO_AIP",
    y="QTDE",
    color="TIPO",
    barmode="group",
    text="QTDE",
    title="Comparativo EO vs PO por Processo (Ordem Cronológica)",
    labels={"PROCESSO_AIP":"Processo","QTDE":"Quantidade","TIPO":"Tipo"},
    category_orders={"PROCESSO_AIP": order_proc},
    color_discrete_map={"EO":"#E53D00","PO":"#F0A202"}
)
chart1.update_traces(textposition="outside")
st.plotly_chart(chart1, use_container_width=True)

# -------------------------
# STEP 3: Compras por PROCESSO e CAM vs EO
# -------------------------
# 1) soma por Processo + CAM
proc_cam = f.groupby(["PROCESSO_AIP","CAM"])["QTDE"].sum().reset_index().rename(columns={"QTDE":"QTDE_CAM"})
# 2) soma de EO por Processo
eo_proc = (
    f[f["TIPO"]=="EO"]
    .groupby("PROCESSO_AIP")["QTDE"]
    .sum()
    .reset_index()
    .rename(columns={"QTDE":"QTDE_EO"})
)
# 3) junta para ter, em cada linha, QTDE_CAM e QTDE_EO
merge_df = proc_cam.merge(eo_proc, on="PROCESSO_AIP", how="left")
# 4) transforma em formato longo para plotar juntos
long = (
    merge_df
    .melt(
        id_vars=["PROCESSO_AIP","CAM"],
        value_vars=["QTDE_CAM","QTDE_EO"],
        var_name="Métrica",
        value_name="Quantidade"
    )
    .replace({"QTDE_CAM":"CAM","QTDE_EO":"EO"})
)

chart2 = px.bar(
    long,
    x="PROCESSO_AIP",
    y="Quantidade",
    color="Métrica",
    barmode="group",
    facet_col="CAM",
    facet_col_wrap=3,
    text="Quantidade",
    title="Comparativo de Compras de Cada CAM vs EO por Processo",
    labels={"PROCESSO_AIP":"Processo","Quantidade":"Qtde","Métrica":""},
    category_orders={"PROCESSO_AIP": order_proc}
)
chart2.update_traces(textposition="outside")
chart2.update_layout(legend_title_text="")
st.plotly_chart(chart2, use_container_width=True)

# -------------------------
# STEP 4: Tabela e Download
# -------------------------
st.markdown("### Detalhes dos Dados Filtrados")
table_df = proc_tipo.drop(columns="EARLIEST_DATE")

gb = GridOptionsBuilder.from_dataframe(table_df)
gb.configure_pagination(paginationAutoPageSize=True)
gb.configure_side_bar()
gb.configure_default_column(groupable=True, editable=True)
grid_opts = gb.build()

AgGrid(table_df, gridOptions=grid_opts, height=400, theme="balham", enable_enterprise_modules=False)

st.download_button(
    "Download Detailed Data as CSV",
    data=table_df.to_csv(index=False).encode("utf-8"),
    file_name="process_summary.csv",
    mime="text/csv"
)
