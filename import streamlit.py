import streamlit as st
import os
import shutil
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# ==========================================
# 1. FUNÇÕES DE FORMATAÇÃO
# ==========================================
def formatar_moeda(valor_str):
    if not valor_str or valor_str == '000':
        return "0,00"
    valor = float(valor_str) / 100
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_doc(documento, tipo):
    if tipo == 'PF' and len(documento) == 11:
        return f"{documento[:3]}.{documento[3:6]}.{documento[6:9]}-{documento[9:]}"
    elif tipo == 'PJ' and len(documento) == 14:
        return f"{documento[:2]}.{documento[2:5]}.{documento[5:8]}/{documento[8:12]}-{documento[12:]}"
    return documento

# ==========================================
# 2. PARSER DO ARQUIVO (Lendo da Memória)
# ==========================================
def ler_arquivo_conteudo(conteudo_texto):
    dados_globais = {
        'ano_calendario': '', 'nome_resp': '', 'cnpj_fonte': '', 'nome_fonte': ''
    }
    beneficiarios_dict = {} 
    registro_atual = None
    codigo_retencao_atual = ""
    
    linhas = conteudo_texto.splitlines()
        
    for linha in linhas:
        partes = linha.strip().split('|')
        if len(partes) < 2: continue
        
        # AQUI ESTÁ A CORREÇÃO: Transformamos a tag em maiúscula para evitar falhas de leitura
        tipo = partes[0].strip().upper() 
        
        if tipo == 'DIRF': dados_globais['ano_calendario'] = partes[2]
        elif tipo == 'RESPO': dados_globais['nome_resp'] = partes[2]
        elif tipo == 'DECPJ':
            dados_globais['cnpj_fonte'] = partes[1]
            dados_globais['nome_fonte'] = partes[2]
        elif tipo == 'IDREC': codigo_retencao_atual = partes[1]
            
        elif tipo in ['BPJDEC', 'BPFDEC']:
            doc = partes[1]
            chave = f"{doc}_{codigo_retencao_atual}"
            
            if chave not in beneficiarios_dict:
                beneficiarios_dict[chave] = {
                    'tipo': 'PJ' if tipo == 'BPJDEC' else 'PF',
                    'doc': doc, 'nome': partes[2], 'codigo_retencao': codigo_retencao_atual, 'registros': []
                }
                
            registro_atual = {
                'rendimentos': ['000'] * 12, 'impostos': ['000'] * 12,
                'previdencia': ['000'] * 12, 'dependentes': ['000'] * 12
            }
            beneficiarios_dict[chave]['registros'].append(registro_atual)
        
        elif tipo == 'RTRT' and registro_atual: registro_atual['rendimentos'] = partes[1:13]
        elif tipo == 'RTPO' and registro_atual: registro_atual['previdencia'] = partes[1:13]
        elif tipo == 'RTDP' and registro_atual: registro_atual['dependentes'] = partes[1:13]
        elif tipo == 'RTIRF' and registro_atual: registro_atual['impostos'] = partes[1:13]
            
    return dados_globais, list(beneficiarios_dict.values())

# ==========================================
# 3. GERADOR DE PDF
# ==========================================
def gerar_pdf(beneficiario, globais, pasta_saida, logo_upload=None):
    nome_arquivo = f"Informe_{beneficiario['doc']}_{beneficiario['codigo_retencao']}.pdf"
    caminho_completo = os.path.join(pasta_saida, nome_arquivo)
    
    doc = SimpleDocTemplate(caminho_completo, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Normal'], alignment=1, fontName="Helvetica-Bold", fontSize=10)
    header_style = ParagraphStyle(name='Header', parent=styles['Normal'], fontName="Helvetica-Bold", fontSize=9, backColor=colors.lightgrey)
    header_style_no_bg = ParagraphStyle(name='HeaderNoBg', parent=styles['Normal'], fontName="Helvetica-Bold", fontSize=9)
    normal_style = ParagraphStyle(name='NormalStyle', parent=styles['Normal'], fontName="Helvetica", fontSize=8)

    txt_titulo = "PESSOA JURÍDICA" if beneficiario['tipo'] == 'PJ' else "PESSOA FÍSICA"
    txt_benef = "2. PESSOA JURÍDICA BENEFICIÁRIA DOS RENDIMENTOS" if beneficiario['tipo'] == 'PJ' else "2. PESSOA FÍSICA BENEFICIÁRIA DOS RENDIMENTOS"
    label_doc = "CNPJ" if beneficiario['tipo'] == 'PJ' else "CPF"

    # Inserção da Logo
    if logo_upload is not None:
        try:
            img = ImageReader(logo_upload)
            iw, ih = img.getSize()
            aspect = ih / float(iw)
            largura_logo = 160
            altura_logo = largura_logo * aspect
            logo = Image(logo_upload, width=largura_logo, height=altura_logo)
            logo.hAlign = 'CENTER'
            elementos.append(logo)
        except Exception as e:
            elementos.append(Paragraph(globais['nome_fonte'], title_style))
    else:
        elementos.append(Paragraph(globais['nome_fonte'], title_style))
        
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(f"COMPROVANTE ANUAL DE RENDIMENTOS PAGOS OU CREDITADOS E DE RETENÇÃO DE IMPOSTO DE<br/>RENDA NA FONTE - {txt_titulo}<br/>Ano-calendário de {globais['ano_calendario']}", title_style))
    elementos.append(Spacer(1, 15))

    elementos.append(Paragraph("1. FONTE PAGADORA", header_style))
    dados_fonte = [
        ["CNPJ", "Nome Empresarial"],
        [formatar_doc(globais['cnpj_fonte'], 'PJ'), globais['nome_fonte']]
    ]
    t_fonte = Table(dados_fonte, colWidths=[120, 415])
    t_fonte.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONT', (0,0), (-1,-1), 'Helvetica', 8),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 8),
    ]))
    elementos.append(t_fonte)
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph(txt_benef, header_style))
    dados_benef = [
        [label_doc, "Nome Empresarial" if beneficiario['tipo'] == 'PJ' else "Nome Completo"],
        [formatar_doc(beneficiario['doc'], beneficiario['tipo']), beneficiario['nome']]
    ]
    t_benef = Table(dados_benef, colWidths=[120, 415])
    t_benef.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONT', (0,0), (-1,-1), 'Helvetica', 8),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 8),
    ]))
    elementos.append(t_benef)
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("3. RENDIMENTO E IMPOSTO RETIDO NA FONTE", header_style))
    
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    if beneficiario['tipo'] == 'PF':
        dados_tabela = [["Mês", "Código de\nretenção", "Rendimento\n(R$)", "Previdência\nOficial (R$)", "Dependentes\n(R$)", "Imposto retido\n(R$)"]]
        colunas_largura = [40, 55, 110, 110, 110, 110]
        alinhamento_direita = (2, 1), (5, -1)
    else:
        dados_tabela = [["Mês", "Código de\nretenção", "Rendimento\n(R$)", "Imposto retido\n(R$)"]]
        colunas_largura = [60, 100, 187.5, 187.5]
        alinhamento_direita = (2, 1), (3, -1)
    
    total_rend, total_prev, total_dep, total_imp = 0, 0, 0, 0

    for i in range(12):
        for reg in beneficiario['registros']:
            rend_str = reg['rendimentos'][i]
            imp_str = reg['impostos'][i]
            
            rend_float = float(rend_str) / 100 if rend_str else 0
            imp_float = float(imp_str) / 100 if imp_str else 0
            
            if beneficiario['tipo'] == 'PF':
                prev_str = reg['previdencia'][i]
                dep_str = reg['dependentes'][i]
                prev_float = float(prev_str) / 100 if prev_str else 0
                dep_float = float(dep_str) / 100 if dep_str else 0
                
                if rend_float == 0 and imp_float == 0 and prev_float == 0 and dep_float == 0:
                    continue
                    
                total_rend += rend_float
                total_imp += imp_float
                total_prev += prev_float
                total_dep += dep_float

                dados_tabela.append([
                    meses[i], beneficiario['codigo_retencao'], formatar_moeda(rend_str), 
                    formatar_moeda(prev_str), formatar_moeda(dep_str), formatar_moeda(imp_str)
                ])
            else:
                if rend_float == 0 and imp_float == 0:
                    continue
                    
                total_rend += rend_float
                total_imp += imp_float

                dados_tabela.append([
                    meses[i], beneficiario['codigo_retencao'], formatar_moeda(rend_str), formatar_moeda(imp_str)
                ])

    if len(dados_tabela) == 1:
        if beneficiario['tipo'] == 'PF':
            dados_tabela.append(["-", "-", "0,00", "0,00", "0,00", "0,00"])
        else:
            dados_tabela.append(["-", "-", "0,00", "0,00"])

    if beneficiario['tipo'] == 'PF':
        dados_tabela.append([
            "Totais", "", f"{total_rend:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"{total_prev:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"{total_dep:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"{total_imp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])
    else:
        dados_tabela.append([
            "Totais", "", f"{total_rend:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
            f"{total_imp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])

    t_rend = Table(dados_tabela, colWidths=colunas_largura)
    t_rend.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 8), ('FONT', (0,1), (-1,-1), 'Helvetica', 8),
        ('ALIGN', alinhamento_direita[0], alinhamento_direita[1], 'RIGHT'), 
        ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke), ('FONT', (0,-1), (-1,-1), 'Helvetica-Bold', 8), 
    ]))
    elementos.append(t_rend)
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph("5. RESPONSÁVEL PELAS INFORMAÇÕES", header_style_no_bg))
    data_assinatura = "28/01/2026" 
    
    dados_resp = [["Nome\n" + globais['nome_resp'], "Data\n" + data_assinatura, "Assinatura\n\n\n"]]
    t_resp = Table(dados_resp, colWidths=[267.5, 100, 167.5])
    t_resp.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black), ('FONT', (0,0), (-1,-1), 'Helvetica', 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elementos.append(t_resp)
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph("Aprovado pela IN/SRF nº 119/2000", normal_style))

    doc.build(elementos)

# ==========================================
# 4. INTERFACE DO STREAMLIT (O "Site")
# ==========================================
st.set_page_config(page_title="Gerador de Informes - Unimed", page_icon="📄")

st.title("Gerador de Informes de Rendimento")
st.markdown("Faça o upload do arquivo da **DIRF (.txt)** para gerar automaticamente os PDFs de todos os fornecedores e credenciados.")

# Campos de Upload
arquivo_txt = st.file_uploader("1. Selecione o arquivo TXT da DIRF", type=['txt'])
arquivo_logo = st.file_uploader("2. Selecione a Logo da Unimed (Opcional)", type=['png', 'jpg', 'jpeg'])

if arquivo_txt is not None:
    if st.button("Gerar PDFs"):
        with st.spinner("Lendo arquivo e gerando PDFs... isso pode levar alguns segundos."):
            # Lê o conteúdo do arquivo enviado
            conteudo = arquivo_txt.getvalue().decode("utf-8", errors="ignore")
            dados_globais, lista_beneficiarios = ler_arquivo_conteudo(conteudo)
            
            # Cria uma pasta temporária para salvar os PDFs
            with tempfile.TemporaryDirectory() as tmpdirname:
                for benef in lista_beneficiarios:
                    gerar_pdf(benef, dados_globais, pasta_saida=tmpdirname, logo_upload=arquivo_logo)
                
                # Zipa a pasta temporária
                shutil.make_archive("Informes_Unimed", 'zip', tmpdirname)
                
            st.success(f"Sucesso! {len(lista_beneficiarios)} informes foram gerados com o ano-calendário de {dados_globais['ano_calendario']}.")
            
            # Botão para baixar o ZIP
            with open("Informes_Unimed.zip", "rb") as f:
                st.download_button(
                    label="📥 Baixar todos os Informes (ZIP)",
                    data=f,
                    file_name="Informes_Unimed.zip",
                    mime="application/zip"
                )