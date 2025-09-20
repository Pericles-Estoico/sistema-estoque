import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sqlite3
import numpy as np
import time
import requests
from io import StringIO

# Configuração da página
st.set_page_config(
    page_title="Sistema de Estoque - Google Sheets",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #4285f4 0%, #34a853 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .sheets-info {
        background: #e8f0fe;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #4285f4;
        margin-bottom: 1rem;
    }
    
    .status-ok { background: #d4edda; color: #155724; padding: 0.5rem; border-radius: 5px; }
    .status-atencao { background: #fff3cd; color: #856404; padding: 0.5rem; border-radius: 5px; }
    .status-critico { background: #f8d7da; color: #721c24; padding: 0.5rem; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# Configuração do Google Sheets
SHEETS_CONFIG = {
    "produtos_url": "",  # Será configurado pelo usuário
    "movimentacoes_url": "",  # Será configurado pelo usuário
}

# Classe para gerenciar dados do Google Sheets
class SheetsManager:
    def __init__(self):
        self.produtos_url = st.session_state.get('produtos_url', '')
        self.movimentacoes_url = st.session_state.get('movimentacoes_url', '')
    
    @st.cache_data(ttl=60)  # Cache por 1 minuto
    def carregar_produtos(_self, url):
        """Carrega produtos do Google Sheets"""
        if not url:
            return pd.DataFrame()
        
        try:
            # Converter URL do Google Sheets para CSV
            if '/edit' in url:
                csv_url = url.replace('/edit#gid=0', '/export?format=csv').replace('/edit', '/export?format=csv')
            else:
                csv_url = url
            
            # Carregar dados
            response = requests.get(csv_url)
            response.raise_for_status()
            
            df = pd.read_csv(StringIO(response.text))
            
            # Validar colunas obrigatórias
            required_cols = ['codigo', 'nome', 'categoria', 'estoque_atual', 'estoque_min', 'estoque_max', 'custo_unitario']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"❌ Colunas faltando na planilha: {missing_cols}")
                return pd.DataFrame()
            
            # Limpar dados
            df = df.dropna(subset=['codigo', 'nome'])
            df['estoque_atual'] = pd.to_numeric(df['estoque_atual'], errors='coerce').fillna(0)
            df['estoque_min'] = pd.to_numeric(df['estoque_min'], errors='coerce').fillna(0)
            df['estoque_max'] = pd.to_numeric(df['estoque_max'], errors='coerce').fillna(0)
            df['custo_unitario'] = pd.to_numeric(df['custo_unitario'], errors='coerce').fillna(0)
            
            return df
            
        except Exception as e:
            st.error(f"❌ Erro ao carregar planilha: {str(e)}")
            return pd.DataFrame()
    
    def adicionar_status_semaforo(self, df):
        """Adiciona colunas de status e semáforo"""
        if df.empty:
            return df
        
        df['status'] = df.apply(lambda row: 
            'CRÍTICO' if row['estoque_atual'] <= row['estoque_min']
            else 'ATENÇÃO' if row['estoque_atual'] <= row['estoque_min'] * 1.5
            else 'OK', axis=1)
        
        df['semaforo'] = df['status'].map({
            'OK': '🟢',
            'ATENÇÃO': '🟡', 
            'CRÍTICO': '🔴'
        })
        
        return df
    
    def salvar_movimentacao_local(self, codigo, tipo, quantidade, motivo=""):
        """Salva movimentação no SQLite local (backup)"""
        conn = sqlite3.connect('movimentacoes_backup.db')
        cursor = conn.cursor()
        
        # Criar tabela se não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                codigo_produto TEXT,
                tipo TEXT,
                quantidade INTEGER,
                motivo TEXT
            )
        ''')
        
        # Inserir movimentação
        cursor.execute('''
            INSERT INTO movimentacoes (codigo_produto, tipo, quantidade, motivo)
            VALUES (?, ?, ?, ?)
        ''', (codigo, tipo, quantidade, motivo))
        
        conn.commit()
        conn.close()

# Inicializar gerenciador
sheets_manager = SheetsManager()

# Header principal
st.markdown("""
<div class="main-header">
    <h1>📊 Sistema de Estoque - Google Sheets</h1>
    <p>Dashboard alimentado diretamente pelo Google Sheets</p>
</div>
""", unsafe_allow_html=True)

# Sidebar - Configuração
st.sidebar.title("⚙️ Configuração")

# URL do Google Sheets
st.sidebar.subheader("🔗 Google Sheets URLs")

produtos_url = st.sidebar.text_input(
    "URL da Planilha de Produtos:",
    value=st.session_state.get('produtos_url', ''),
    placeholder="https://docs.google.com/spreadsheets/d/..."
)

if produtos_url != st.session_state.get('produtos_url', ''):
    st.session_state['produtos_url'] = produtos_url
    st.cache_data.clear()

# Instruções
with st.sidebar.expander("📋 Como configurar"):
    st.markdown("""
    **1. Criar Google Sheets:**
    - Colunas: codigo, nome, categoria, estoque_atual, estoque_min, estoque_max, custo_unitario
    
    **2. Compartilhar:**
    - File → Share → "Anyone with link can view"
    
    **3. Copiar URL:**
    - Cole a URL completa aqui
    """)

# Botões de controle
col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("🔄 Atualizar"):
        st.cache_data.clear()
        st.rerun()

with col_btn2:
    auto_refresh = st.checkbox("Auto 30s", value=False)

if auto_refresh:
    time.sleep(30)
    st.rerun()

# Verificar configuração
if not produtos_url:
    st.markdown("""
    <div class="sheets-info">
        <h3>🚀 Primeiros Passos</h3>
        <p><strong>1.</strong> Crie uma planilha no Google Sheets com as colunas:</p>
        <code>codigo | nome | categoria | estoque_atual | estoque_min | estoque_max | custo_unitario</code>
        <p><strong>2.</strong> Compartilhe como "Anyone with link can view"</p>
        <p><strong>3.</strong> Cole a URL na barra lateral</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Exemplo de planilha
    st.subheader("📋 Exemplo de Planilha")
    exemplo_df = pd.DataFrame({
        'codigo': ['P001', 'P002', 'P003'],
        'nome': ['Produto A', 'Produto B', 'Produto C'],
        'categoria': ['Eletrônicos', 'Roupas', 'Casa'],
        'estoque_atual': [150, 30, 80],
        'estoque_min': [50, 40, 60],
        'estoque_max': [300, 200, 250],
        'custo_unitario': [25.50, 15.75, 32.00]
    })
    st.dataframe(exemplo_df, use_container_width=True)
    st.stop()

# Carregar dados do Google Sheets
produtos_df = sheets_manager.carregar_produtos(produtos_url)

if produtos_df.empty:
    st.error("❌ Não foi possível carregar dados da planilha. Verifique a URL e permissões.")
    st.stop()

# Adicionar status e semáforo
produtos_df = sheets_manager.adicionar_status_semaforo(produtos_df)

# Informações da conexão
st.markdown(f"""
<div class="sheets-info">
    ✅ <strong>Conectado ao Google Sheets</strong> | 
    📊 {len(produtos_df)} produtos carregados | 
    🕐 Última atualização: {datetime.now().strftime('%H:%M:%S')}
</div>
""", unsafe_allow_html=True)

# Métricas principais
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_produtos = len(produtos_df)
    st.metric("📦 Total Produtos", total_produtos)

with col2:
    produtos_ok = len(produtos_df[produtos_df['status'] == 'OK'])
    st.metric("🟢 OK", produtos_ok, delta=f"{produtos_ok/total_produtos*100:.1f}%")

with col3:
    produtos_atencao = len(produtos_df[produtos_df['status'] == 'ATENÇÃO'])
    st.metric("🟡 Atenção", produtos_atencao, delta=f"{produtos_atencao/total_produtos*100:.1f}%")

with col4:
    produtos_criticos = len(produtos_df[produtos_df['status'] == 'CRÍTICO'])
    st.metric("🔴 Crítico", produtos_criticos, delta=f"{produtos_criticos/total_produtos*100:.1f}%")

# Layout principal
col_left, col_right = st.columns([2, 1])

with col_left:
    # Tabela de produtos com semáforos
    st.subheader("📊 Mapa de Semáforos")
    
    # Filtros
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        categoria_filter = st.selectbox(
            "Filtrar por categoria:",
            ['Todas'] + list(produtos_df['categoria'].unique())
        )
    
    with col_f2:
        status_filter = st.selectbox(
            "Filtrar por status:",
            ['Todos', 'CRÍTICO', 'ATENÇÃO', 'OK']
        )
    
    # Aplicar filtros
    df_filtrado = produtos_df.copy()
    if categoria_filter != 'Todas':
        df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filter]
    if status_filter != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['status'] == status_filter]
    
    # Exibir tabela
    st.dataframe(
        df_filtrado[['semaforo', 'codigo', 'nome', 'categoria', 'estoque_atual', 'estoque_min', 'status']],
        use_container_width=True,
        height=400
    )

with col_right:
    # Gráfico de pizza - Status
    st.subheader("📈 Distribuição por Status")
    
    status_counts = produtos_df['status'].value_counts()
    
    fig_pie = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        color=status_counts.index,
        color_discrete_map={
            'OK': '#27ae60',
            'ATENÇÃO': '#f39c12',
            'CRÍTICO': '#e74c3c'
        }
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    fig_pie.update_layout(height=300)
    st.plotly_chart(fig_pie, use_container_width=True)
    
    # Alertas
    st.subheader("🚨 Alertas")
    produtos_criticos_lista = produtos_df[produtos_df['status'] == 'CRÍTICO']
    
    if len(produtos_criticos_lista) > 0:
        for _, produto in produtos_criticos_lista.iterrows():
            st.error(f"🔴 **{produto['nome']}** - Estoque: {produto['estoque_atual']} (Mín: {produto['estoque_min']})")
    else:
        st.success("✅ Nenhum produto em situação crítica!")

# Gráfico de evolução por categoria
st.subheader("📊 Análise por Categoria")

col_cat1, col_cat2 = st.columns([2, 1])

with col_cat1:
    # Gráfico de barras por categoria
    categoria_stats = produtos_df.groupby('categoria').agg({
        'estoque_atual': 'sum',
        'codigo': 'count'
    }).reset_index()
    categoria_stats.columns = ['categoria', 'estoque_total', 'qtd_produtos']
    
    fig_bar = px.bar(
        categoria_stats,
        x='categoria',
        y='estoque_total',
        title="Estoque Total por Categoria",
        color='estoque_total',
        color_continuous_scale='viridis'
    )
    fig_bar.update_layout(height=400)
    st.plotly_chart(fig_bar, use_container_width=True)

with col_cat2:
    st.subheader("📋 Resumo por Categoria")
    for _, row in categoria_stats.iterrows():
        st.metric(
            f"📦 {row['categoria']}", 
            f"{row['estoque_total']:.0f} un",
            delta=f"{row['qtd_produtos']} produtos"
        )

# Seção de movimentações (simulada)
st.subheader("➕ Registrar Movimentação")
st.info("💡 **Dica**: As movimentações são salvas localmente. Para integração completa, configure uma planilha de movimentações.")

col_mov1, col_mov2, col_mov3, col_mov4 = st.columns(4)

with col_mov1:
    mov_produto = st.selectbox(
        "Produto:",
        produtos_df['codigo'].tolist(),
        format_func=lambda x: f"{x} - {produtos_df[produtos_df['codigo']==x]['nome'].iloc[0]}",
        key="mov_produto"
    )

with col_mov2:
    mov_tipo = st.selectbox("Tipo:", ["entrada", "saida"])

with col_mov3:
    mov_quantidade = st.number_input("Quantidade:", min_value=1, value=1)

with col_mov4:
    mov_motivo = st.text_input("Motivo:", placeholder="Ex: Compra, Venda...")

if st.button("✅ Registrar Movimentação", type="primary"):
    try:
        sheets_manager.salvar_movimentacao_local(mov_produto, mov_tipo, mov_quantidade, mov_motivo)
        st.success(f"✅ Movimentação salva localmente: {mov_tipo} de {mov_quantidade} unidades")
        st.info("💡 Para atualizar o estoque, edite diretamente na planilha do Google Sheets")
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")

# Instruções finais
st.markdown("---")
st.markdown("""
### 🔄 **Como Funciona a Integração:**

1. **📊 Dados em Tempo Real**: Dashboard lê diretamente do Google Sheets
2. **✏️ Edição Fácil**: Modifique produtos diretamente na planilha
3. **🔄 Atualização Automática**: Cache de 1 minuto para performance
4. **👥 Colaborativo**: Múltiplos usuários podem editar a planilha
5. **💾 Backup Local**: Movimentações salvas localmente como backup

### 📋 **Próximos Passos:**
- Configure uma segunda planilha para movimentações
- Adicione fórmulas no Sheets para cálculos automáticos
- Use Google Apps Script para automações avançadas
""")

# Footer
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>📊 Sistema de Estoque integrado com Google Sheets | Última atualização: {}</p>
</div>
""".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")), unsafe_allow_html=True)
