import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sqlite3
import numpy as np
import time

# Configuração da página
st.set_page_config(
    page_title="Sistema de Fluxo de Estoque",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #3498db;
    }
    
    .status-ok {
        background: linear-gradient(90deg, #27ae60, #2ecc71);
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
    }
    
    .status-atencao {
        background: linear-gradient(90deg, #f39c12, #e67e22);
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
    }
    
    .status-critico {
        background: linear-gradient(90deg, #e74c3c, #c0392b);
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Classe para gerenciar o banco de dados
class EstoqueDB:
    def __init__(self, db_path="estoque.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela produtos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS produtos (
                codigo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                categoria TEXT,
                estoque_atual INTEGER DEFAULT 0,
                estoque_min INTEGER DEFAULT 0,
                estoque_max INTEGER DEFAULT 0,
                custo_unitario REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela movimentações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                codigo_produto TEXT,
                tipo TEXT CHECK(tipo IN ('entrada', 'saida')),
                quantidade INTEGER,
                motivo TEXT,
                saldo_anterior INTEGER,
                saldo_atual INTEGER,
                usuario TEXT DEFAULT 'streamlit',
                FOREIGN KEY (codigo_produto) REFERENCES produtos (codigo)
            )
        ''')
        
        conn.commit()
        conn.close()
        self.inserir_dados_iniciais()
    
    def inserir_dados_iniciais(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM produtos")
        if cursor.fetchone()[0] == 0:
            produtos = [
                ("P001", "Produto A", "Eletrônicos", 150, 50, 300, 25.50),
                ("P002", "Produto B", "Eletrônicos", 30, 40, 200, 15.75),
                ("P003", "Produto C", "Roupas", 80, 60, 250, 32.00),
                ("P004", "Produto D", "Roupas", 200, 100, 400, 18.25),
                ("P005", "Produto E", "Casa", 45, 50, 180, 42.80),
                ("P006", "Produto F", "Casa", 120, 30, 200, 28.90),
                ("P007", "Produto G", "Livros", 75, 25, 150, 12.50),
                ("P008", "Produto H", "Livros", 15, 20, 100, 35.00)
            ]
            
            cursor.executemany('''
                INSERT INTO produtos (codigo, nome, categoria, estoque_atual, estoque_min, estoque_max, custo_unitario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', produtos)
            
            conn.commit()
        conn.close()
    
    def obter_produtos(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('''
            SELECT codigo, nome, categoria, estoque_atual, estoque_min, estoque_max, custo_unitario
            FROM produtos ORDER BY nome
        ''', conn)
        conn.close()
        
        # Adicionar status e semáforo
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
    
    def registrar_movimentacao(self, codigo, tipo, quantidade, motivo=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Obter estoque atual
            cursor.execute("SELECT estoque_atual FROM produtos WHERE codigo = ?", (codigo,))
            resultado = cursor.fetchone()
            
            if not resultado:
                raise ValueError(f"Produto {codigo} não encontrado")
            
            saldo_anterior = resultado[0]
            
            # Calcular novo saldo
            if tipo == "entrada":
                saldo_atual = saldo_anterior + quantidade
            else:  # saida
                if saldo_anterior < quantidade:
                    raise ValueError("Estoque insuficiente")
                saldo_atual = saldo_anterior - quantidade
            
            # Registrar movimentação
            cursor.execute('''
                INSERT INTO movimentacoes (codigo_produto, tipo, quantidade, motivo, saldo_anterior, saldo_atual)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (codigo, tipo, quantidade, motivo, saldo_anterior, saldo_atual))
            
            # Atualizar estoque
            cursor.execute("UPDATE produtos SET estoque_atual = ? WHERE codigo = ?", (saldo_atual, codigo))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def obter_historico(self, codigo=None, dias=30):
        conn = sqlite3.connect(self.db_path)
        
        if codigo:
            query = '''
                SELECT DATE(data_hora) as data, saldo_atual, codigo_produto
                FROM movimentacoes 
                WHERE codigo_produto = ? AND data_hora >= datetime('now', '-{} days')
                ORDER BY data_hora
            '''.format(dias)
            df = pd.read_sql_query(query, conn, params=(codigo,))
        else:
            query = '''
                SELECT data_hora, codigo_produto, tipo, quantidade, motivo, saldo_atual
                FROM movimentacoes 
                WHERE data_hora >= datetime('now', '-{} days')
                ORDER BY data_hora DESC
            '''.format(dias)
            df = pd.read_sql_query(query, conn)
        
        conn.close()
        return df

# Inicializar banco de dados
@st.cache_resource
def init_db():
    return EstoqueDB()

db = init_db()

# Header principal
st.markdown("""
<div class="main-header">
    <h1>📦 Sistema de Fluxo de Estoque</h1>
    <p>Dashboard Interativo com Semáforos em Tempo Real</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("🔧 Controles")

# Auto-refresh
auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (30s)", value=False)
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Botão de refresh manual
if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

# Obter dados
produtos_df = db.obter_produtos()

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
    
    # Configurar cores para a tabela
    def color_status(val):
        if val == 'CRÍTICO':
            return 'background-color: #ffebee; color: #c62828'
        elif val == 'ATENÇÃO':
            return 'background-color: #fff8e1; color: #ef6c00'
        else:
            return 'background-color: #e8f5e8; color: #2e7d32'
    
    # Exibir tabela estilizada
    styled_df = produtos_df[['semaforo', 'codigo', 'nome', 'categoria', 'estoque_atual', 'estoque_min', 'status']].style.applymap(
        color_status, subset=['status']
    )
    
    st.dataframe(styled_df, use_container_width=True, height=400)

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

# Gráficos de evolução
st.subheader("📈 Evolução do Estoque")

# Seletor de produto
produto_selecionado = st.selectbox(
    "Selecione um produto:",
    produtos_df['codigo'].tolist(),
    format_func=lambda x: f"{x} - {produtos_df[produtos_df['codigo']==x]['nome'].iloc[0]}"
)

if produto_selecionado:
    historico_df = db.obter_historico(produto_selecionado)
    produto_info = produtos_df[produtos_df['codigo'] == produto_selecionado].iloc[0]
    
    if len(historico_df) > 0:
        # Gráfico de linha
        fig_line = go.Figure()
        
        # Linha do estoque
        fig_line.add_trace(go.Scatter(
            x=historico_df['data'],
            y=historico_df['saldo_atual'],
            mode='lines+markers',
            name='Estoque Atual',
            line=dict(color='#3498db', width=3)
        ))
        
        # Linha do estoque mínimo
        fig_line.add_hline(
            y=produto_info['estoque_min'],
            line_dash="dash",
            line_color="red",
            annotation_text="Estoque Mínimo"
        )
        
        # Linha do estoque máximo
        fig_line.add_hline(
            y=produto_info['estoque_max'],
            line_dash="dash", 
            line_color="green",
            annotation_text="Estoque Máximo"
        )
        
        fig_line.update_layout(
            title=f"Evolução - {produto_info['nome']}",
            xaxis_title="Data",
            yaxis_title="Quantidade",
            height=400
        )
        
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("📊 Sem histórico disponível para este produto")

# Seção de movimentações
st.subheader("➕ Registrar Movimentação")

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
        db.registrar_movimentacao(mov_produto, mov_tipo, mov_quantidade, mov_motivo)
        st.success(f"✅ Movimentação registrada: {mov_tipo} de {mov_quantidade} unidades")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")

# Histórico recente
st.subheader("📋 Movimentações Recentes")
historico_recente = db.obter_historico(dias=7)

if len(historico_recente) > 0:
    # Formatar data
    historico_recente['data_hora'] = pd.to_datetime(historico_recente['data_hora']).dt.strftime('%d/%m/%Y %H:%M')
    
    st.dataframe(
        historico_recente[['data_hora', 'codigo_produto', 'tipo', 'quantidade', 'motivo', 'saldo_atual']],
        use_container_width=True,
        height=300
    )
else:
    st.info("📋 Nenhuma movimentação recente")

# Análises por categoria
st.subheader("📊 Análise por Categoria")

categoria_stats = produtos_df.groupby('categoria').agg({
    'estoque_atual': 'sum',
    'codigo': 'count',
    'custo_unitario': 'mean'
}).round(2)

categoria_stats.columns = ['Estoque Total', 'Qtd Produtos', 'Custo Médio']

# Gráfico de barras por categoria
fig_bar = px.bar(
    x=categoria_stats.index,
    y=categoria_stats['Estoque Total'],
    title="Estoque Total por Categoria",
    color=categoria_stats['Estoque Total'],
    color_continuous_scale='viridis'
)
fig_bar.update_layout(height=400)

col_cat1, col_cat2 = st.columns([2, 1])

with col_cat1:
    st.plotly_chart(fig_bar, use_container_width=True)

with col_cat2:
    st.dataframe(categoria_stats, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>📦 Sistema de Fluxo de Estoque v2.0 | Desenvolvido com Streamlit</p>
    <p>🔄 Última atualização: {}</p>
</div>
""".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")), unsafe_allow_html=True)
