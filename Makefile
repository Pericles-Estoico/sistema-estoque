# Makefile para Sistema de Fluxo de Estoque

# Variáveis
PYTHON = python3
PIP = pip3
APP = dashboard_streamlit.py

# Comandos principais
.PHONY: install run clean deploy help

# Instalar dependências
install:
	@echo "📦 Instalando dependências..."
	$(PIP) install -r requirements.txt
	@echo "✅ Instalação concluída!"

# Executar aplicação
run:
	@echo "🚀 Iniciando dashboard Streamlit..."
	streamlit run $(APP) --server.port 8501 --server.address 0.0.0.0

# Executar em modo desenvolvimento
dev:
	@echo "🔧 Modo desenvolvimento..."
	streamlit run $(APP) --server.runOnSave true

# Limpar cache e arquivos temporários
clean:
	@echo "🧹 Limpando arquivos temporários..."
	rm -rf __pycache__/
	rm -rf .streamlit/
	rm -f *.pyc
	@echo "✅ Limpeza concluída!"

# Preparar para deploy no GitHub
deploy:
	@echo "🚀 Preparando deploy..."
	git add .
	git status
	@echo "Execute: git commit -m 'Deploy sistema estoque' && git push"

# Backup do banco de dados
backup:
	@echo "💾 Fazendo backup do banco..."
	cp estoque.db backup_estoque_$(shell date +%Y%m%d_%H%M%S).db
	@echo "✅ Backup criado!"

# Testar aplicação
test:
	@echo "🧪 Testando aplicação..."
	$(PYTHON) -c "import streamlit; import pandas; import plotly; print('✅ Todas as dependências OK!')"

# Gerar dados de exemplo
sample-data:
	@echo "📊 Gerando dados de exemplo..."
	$(PYTHON) -c "from dashboard_streamlit import EstoqueDB; db = EstoqueDB(); print('✅ Banco inicializado!')"

# Mostrar ajuda
help:
	@echo "📋 Comandos disponíveis:"
	@echo "  make install     - Instalar dependências"
	@echo "  make run         - Executar aplicação"
	@echo "  make dev         - Modo desenvolvimento"
	@echo "  make clean       - Limpar arquivos temporários"
	@echo "  make deploy      - Preparar para deploy"
	@echo "  make backup      - Backup do banco de dados"
	@echo "  make test        - Testar dependências"
	@echo "  make sample-data - Gerar dados de exemplo"
	@echo "  make help        - Mostrar esta ajuda"

# Comando padrão
all: install test run
