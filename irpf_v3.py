import re
import io
from typing import List, Tuple, Dict, Optional

import streamlit as st
import pandas as pd
import pdfplumber

# ===== DICIONÁRIO COMPLETO (GRUPO, CÓDIGO, DESCRIÇÃO) =====
CODIGOS_LIST = [
    ("01","01","Prédio residencial"), ("01","02","Prédio comercial"), ("01","03","Galpão"),
    ("01","11","Apartamento"), ("01","12","Casa"), ("01","13","Terreno"),
    ("01","14","Imóvel rural (ver item Imóvel rural)"), ("01","15","Sala ou conjunto"),
    ("01","16","Construção"), ("01","17","Benfeitorias (ver item Benfeitorias)"),
    ("01","18","Loja"), ("01","99","Outros bens imóveis"),
    ("02","01","Veículo automotor terrestre: caminhão, automóvel, moto etc."),
    ("02","02","Aeronave"), ("02","03","Embarcação"),
    ("02","04","Bem relacionado à atividade autônoma com o exercício de profissão"),
    ("02","05","Joia, quadro, objeto de arte, de coleção, antiguidade etc."),
    ("02","99","Outros bens móveis"),
    ("03","01","Ações (inclusive as listadas em bolsa)"),
    ("03","02","Quotas ou quinhões de capital"),
    ("03","99","Outras participações societárias"),
    ("04","01","Depósito em conta poupança"),
    ("04","02","Títulos públicos e privados sujeitos à tributação (Tesouro Direto, CDB, RDB e outros)"),
    ("04","03","Títulos isentos de tributação (LCI, LCA, CRI, CRA, LIG, Debêntures de Infraestrutura e outros)"),
    ("04","04","Ativos negociados em bolsa no Brasil (BDRs, opções e outros – exceto ações e fundos)"),
    ("04","05","Ouro, ativo financeiro"),
    ("04","99","Outras aplicações e investimentos"),
    ("05","01","Empréstimos concedidos"), ("05","02","Crédito decorrente de alienação"),
    ("05","99","Outros créditos"),
    ("06","01","Depósito em conta-corrente ou conta pagamento"),
    ("06","10","Dinheiro em espécie – moeda nacional"),
    ("06","11","Dinheiro em espécie – moeda estrangeira"),
    ("06","99","Outros depósitos à vista"),
    ("07","01","Fundos de Investimentos sujeitos à tributação periódica (come-cotas)"),
    ("07","02","Fundos de Investimento nas Cadeias Produtivas Agroindustriais (Fiagro)"),
    ("07","03","Fundos de Investimento Imobiliário (FII)"),
    ("07","04","Fundos de Investimento em Ações e Fundos Mútuos de Privatização – FGTS"),
    ("07","05","Fundos de Investimento em Ações – Mercado de Acesso"),
    ("07","06","Fundos de Investimento em Participações, em Cotas de Fundos de Investimento em Participações e em Empresas Emergentes"),
    ("07","07","FIP-IE e FIP-PD&I"),
    ("07","08","Fundos de Índice de Renda Fixa – Lei 13.043/14"),
    ("07","09","Demais ETFs"), ("07","10","FIDC"),
    ("07","11","Fundos sem tributação periódica"), ("07","99","Outros fundos"),
    ("08","01","Criptoativo Bitcoin (BTC)"),
    ("08","02","Altcoins (ETH, XRP, BCH, LTC etc.)"),
    ("08","03","Stablecoins (USDT, USDC, BRZ, BUSD, DAI, TUSD, GUSD, PAX, PAXG etc.)"),
    ("08","10","NFTs"), ("08","99","Outros criptoativos"),
    ("99","01","Licença e concessão especiais"),
    ("99","02","Título de clube e assemelhado"),
    ("99","03","Direito de autor, de inventor e patente"),
    ("99","04","Direito de lavra e assemelhado"),
    ("99","05","Consórcio não contemplado (ver item Consórcios)"),
    ("99","06","VGBL – Vida Gerador de Benefício Livre"),
    ("99","07","Juros Sobre Capital Próprio Creditado, mas não Pago"),
    ("99","99","Outros bens e direitos"),
]

GRUPOS_TXT = """**Dicionário de Grupos (Bens e Direitos)**  
01 – Bens Imóveis  
02 – Bens Móveis  
03 – Participações Societárias  
04 – Aplicações e Investimentos Financeiros  
05 – Créditos  
06 – Depósitos à vista e Numerário  
07 – Fundos  
08 – Criptoativos  
99 – Outros Bens e Direitos
"""

RESSALVA_TXT = (
    "🔎 **Ressalva importante:** As **ações negociadas em bolsa** devem ser declaradas como "
    "**Participações Societárias** no IRPF. Assim, o totalizador de “Participações Societárias” "
    "no quadro resumo contempla tanto as participações acionárias em **S.As. de capital aberto** "
    "quanto em **S.As. de capital fechado**."
)

# ===== REGEX & UTIL =====
BRL_NUM = r'(?:\d{1,3}(?:\.\d{3})*,\d{2}|0,00)'
ITEM_ANCHOR = re.compile(r'^\s*(\d{2})\s+(\d{2})\s+(.*)$', re.MULTILINE)

def brl_to_float(s: str) -> float:
    s = s.strip().replace('.', '').replace(',', '.')
    try: return float(s)
    except Exception: return 0.0

def format_brl(value: float) -> str:
    """Formata número como R$ X.XXX,XX (entrada deve ser numérica)."""
    if value is None or (isinstance(value, float) and pd.isna(value)): 
        return ""
    # garante conversão caso venha string por engano
    try:
        v = float(str(value).replace(".", "").replace(",", "."))
    except Exception:
        v = 0.0
    return f"R$ {v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def load_codigos_embutidos() -> pd.DataFrame:
    df = pd.DataFrame(CODIGOS_LIST, columns=["grupo","codigo","descricao"])
    df["grupo"]  = df["grupo"].astype(str).str.zfill(2)
    df["codigo"] = df["codigo"].astype(str).str.zfill(2)
    return df

def read_pdf_text(uploaded_file) -> str:
    with pdfplumber.open(uploaded_file) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def detect_year_headers(text: str) -> Tuple[str, str]:
    years = sorted(set(re.findall(r'31/12/(\d{4})', text)))
    return (years[-2], years[-1]) if len(years) >= 2 else ('ano_1','ano_2')

def extract_section(full_text: str, start_marker: str, stop_markers: List[str]) -> str:
    start_idx = full_text.find(start_marker)
    if start_idx == -1: return ""
    tail = full_text[start_idx:]
    stop_idx = min([tail.find(m) for m in stop_markers if tail.find(m) != -1] or [len(tail)])
    return tail[:stop_idx]

def split_items(section_text: str):
    matches = list(ITEM_ANCHOR.finditer(section_text))
    items = []
    for i, m in enumerate(matches):
        g, c = m.group(1), m.group(2)
        end = matches[i+1].start() if i+1 < len(matches) else len(section_text)
        chunk = section_text[m.start():end]
        items.append((g, c, chunk))
    return items

def extract_values_from_chunk(chunk: str):
    first_line = (chunk.splitlines() or [chunk])[0]
    money_in_line = re.findall(BRL_NUM, first_line)
    if len(money_in_line) >= 2:
        return brl_to_float(money_in_line[-2]), brl_to_float(money_in_line[-1])
    money_all = re.findall(BRL_NUM, chunk)
    if len(money_all) >= 2:
        return brl_to_float(money_all[-2]), brl_to_float(money_all[-1])
    return None, None

def parse_bens_direitos_from_text(full_text: str) -> Tuple[pd.DataFrame, Tuple[str,str]]:
    section = extract_section(
        full_text,
        start_marker="DECLARAÇÃO DE BENS E DIREITOS",
        stop_markers=["DÍVIDAS E ÔNUS","RENDIMENTOS","EVOLUÇÃO PATRIMONIAL","OUTRAS INFORMAÇÕES"]
    )
    if not section.strip():
        raise RuntimeError("Seção 'DECLARAÇÃO DE BENS E DIREITOS' não encontrada no PDF.")
    ano1, ano2 = detect_year_headers(section)
    recs = []
    for grupo, codigo, chunk in split_items(section):
        v1, v2 = extract_values_from_chunk(chunk)
        if v1 is None or v2 is None: v1, v2 = 0.0, 0.0
        recs.append({"grupo":str(grupo).zfill(2),"codigo":str(codigo).zfill(2),
                     f"situacao_{ano1}":v1, f"situacao_{ano2}":v2})
    df = pd.DataFrame(recs)
    if df.empty: return df, (ano1, ano2)
    num_cols = [c for c in df.columns if c.startswith("situacao_")]
    df = df.groupby(["grupo","codigo"], as_index=False)[num_cols].sum(numeric_only=True)
    return df, (ano1, ano2)

def anexar_descricao(df_vals: pd.DataFrame, df_cod: pd.DataFrame) -> pd.DataFrame:
    merged = df_vals.merge(df_cod.drop_duplicates(), on=["grupo","codigo"], how="left")
    cols = ["grupo","codigo","descricao"] + [c for c in merged.columns if c.startswith("situacao_")]
    return merged[cols]

def resumir_por_grupo_codigo(df_vals: pd.DataFrame) -> pd.DataFrame:
    num_cols = [c for c in df_vals.columns if c.startswith("situacao_")]
    return (df_vals.groupby(["grupo","codigo","descricao"], as_index=False)[num_cols]
            .sum(numeric_only=True))

def add_total_row(df_num: pd.DataFrame) -> pd.DataFrame:
    """Adiciona linha TOTAL somando colunas numéricas de situação."""
    num_cols = [c for c in df_num.columns if c.startswith("situacao_")]
    total_vals = {c: df_num[c].sum() for c in num_cols}
    total_row = {"grupo":"", "codigo":"", "descricao":"TOTAL", **total_vals}
    return pd.concat([df_num, pd.DataFrame([total_row])], ignore_index=True)

def extract_declarant_info(full_text: str) -> Dict[str, Optional[str]]:
    cpf = None
    m = re.search(r'CPF[:\s]*((?:\d{3}\.\d{3}\.\d{3}-\d{2})|\d{11})', full_text, re.I)
    if m: cpf = m.group(1).strip()
    dob = None
    m = re.search(r'(?:Data de nascimento|Nascimento|Nascido em)[:\s\-]*?(\d{2}/\d{2}/\d{4})', full_text, re.I)
    if m: dob = m.group(1).strip()
    nome = None
    for label in [r'Nome do contribuinte', r'Nome', r'Declarante', r'Contribuinte', r'NOME']:
        m = re.search(rf'{label}\s*[:\-]?\s*([A-ZÀ-Ý][A-Za-zÀ-ÿ0-9\.\- \u00C0-\u017F,/]{{2,120}})', full_text, re.I)
        if m:
            candidate = m.group(1).strip().strip(':')
            if 2 < len(candidate) < 160:
                nome = candidate; break
    return {"Nome": nome, "CPF": cpf, "Data de Nascimento": dob}

def make_excel_bytes(df_decl: pd.DataFrame, df_resumo_num: pd.DataFrame) -> bytes:
    """Gera Excel com valores já formatados como 'R$ ...' e linha TOTAL."""
    buf = io.BytesIO()
    df_out = add_total_row(df_resumo_num.copy())
    # formata valores em texto BRL
    for c in [col for col in df_out.columns if col.startswith("situacao_")]:
        df_out[c] = df_out[c].apply(format_brl)
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df_decl.to_excel(xw, index=False, sheet_name="declarante")
        df_out.to_excel(xw, index=False, sheet_name="resumo_por_codigo")
    buf.seek(0)
    return buf.read()

# ===== UI STREAMLIT =====
st.set_page_config(page_title="IRPF • Bens e Direitos (Resumo por Código)", page_icon="📄", layout="wide")
st.title("📄 IRPF • Bens e Direitos → Resumo por (Grupo, Código)")
st.caption("Envie o PDF da declaração. O dicionário de códigos já está embutido no app.")

with st.expander("ℹ️ Dicionário de Grupos e Observações", expanded=False):
    st.markdown(GRUPOS_TXT)
    st.markdown(RESSALVA_TXT)

uploaded = st.file_uploader("Envie o PDF do IRPF", type=["pdf"])

if uploaded is not None:
    try:
        with st.spinner("Lendo PDF..."):
            full_text = read_pdf_text(uploaded)

        info = extract_declarant_info(full_text)
        df_decl = pd.DataFrame([info])

        with st.spinner("Extraindo e somando por (Grupo, Código)..."):
            df_vals, (ano1, ano2) = parse_bens_direitos_from_text(full_text)

        st.subheader("Declarante")
        st.dataframe(df_decl, use_container_width=True)

        if df_vals.empty:
            st.warning("Não foram encontrados itens na seção 'Declaração de Bens e Direitos'.")
        else:
            df_cod = load_codigos_embutidos()
            df_temp = anexar_descricao(df_vals, df_cod)
            df_resumo_num = resumir_por_grupo_codigo(df_temp)  # NUMÉRICO
            df_resumo_num = add_total_row(df_resumo_num)

            # versão apenas para exibir (strings BRL)
            df_resumo_display = df_resumo_num.copy()
            for c in [col for col in df_resumo_display.columns if c.startswith("situacao_")]:
                df_resumo_display[c] = df_resumo_display[c].apply(format_brl)

            st.success(f"Anos detectados: **{ano1}** e **{ano2}**")
            st.subheader("Resumo por (Grupo, Código)")
            st.dataframe(df_resumo_display, use_container_width=True)

            xlsx_bytes = make_excel_bytes(df_decl, df_resumo_num)  # passa o NUMÉRICO
            st.download_button(
                label="⬇️ Baixar Excel (declarante + resumo_por_codigo)",
                data=xlsx_bytes,
                file_name="saida_irpf_bens_direitos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Erro ao processar o PDF: {e}")
else:
    st.info("Faça o upload do PDF para iniciar.")

