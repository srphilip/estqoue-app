# app.py (Código final para Render.com com PostgreSQL)

from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from datetime import datetime
import os
import random
import psycopg2 
from psycopg2 import extras 

# --- VARIÁVEIS DE CONEXÃO POSTGRES ---
# O Render fornece a URL completa via variável de ambiente 'DATABASE_URL'
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Corrigir o formato da URL para a biblioteca psycopg2
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# Variáveis locais de fallback (apenas para testar no seu PC antes do deploy)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "estoque_db") 
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "sua_senha_secreta_local") 
DB_PORT = os.environ.get("DB_PORT", "5432")

app = Flask(__name__)


# --- Funções de Banco de Dados ---

def get_db_connection():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
        else:
            # Conexão local para testes
            conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)
        return conn
    except Exception as e:
        print(f"ERRO DE CONEXÃO AO POSTGRES: {e}")
        raise ConnectionError("Falha na conexão com o banco de dados PostgreSQL.")

def executar_query(query, params=None, fetch_mode='none'):
    """Função centralizada para executar comandos e queries no PG."""
    conn = None
    resultado = None
    try:
        conn = get_db_connection()
        # Usamos DictCursor para que os resultados venham como dicionários (fácil para Flask e Pandas)
        cur = conn.cursor(cursor_factory=extras.DictCursor)
        cur.execute(query, params)
        
        if fetch_mode == 'one':
            resultado = cur.fetchone()
        elif fetch_mode == 'all':
            # Converte os resultados do cursor para lista de dicionários padrão
            resultado = [dict(row) for row in cur.fetchall()]
        
        conn.commit()
        cur.close()
        return resultado
    
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro na execução da Query: {e}")
        return [] if fetch_mode == 'all' else None 
    finally:
        if conn:
            conn.close()

def gerar_proximo_codigo():
    """Busca o ID máximo para gerar o próximo código (P001, P002...)."""
    query = 'SELECT MAX(id) FROM produtos'
    resultado = executar_query(query, fetch_mode='one') 
    
    last_id = resultado[0] if resultado and resultado[0] is not None else 0 
    
    next_id = last_id + 1
    return f'P{next_id:03d}' 

def create_table():
    """Cria as tabelas de produtos e movimentações no PostgreSQL."""
    # Tabela PRODUTOS (com SERIAL PRIMARY KEY e VARCHAR)
    query_produtos = '''
        CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            codigo VARCHAR(10) UNIQUE NOT NULL,  
            nome VARCHAR(255) NOT NULL,
            categoria VARCHAR(100),
            quantidade INTEGER NOT NULL,
            valor_unitario NUMERIC(10, 2),
            data_cadastro VARCHAR(50)
        );
    '''
    executar_query(query_produtos)
    
    # Tabela MOVIMENTACOES (para auditoria)
    query_movimentacoes = '''
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id SERIAL PRIMARY KEY,
            produto_id INTEGER REFERENCES produtos(id), 
            tipo VARCHAR(50) NOT NULL, -- ENTRADA, SAIDA, AJUSTE_ENTRADA, AJUSTE_SAIDA
            quantidade INTEGER NOT NULL,
            data_movimentacao VARCHAR(50)
        );
    '''
    executar_query(query_movimentacoes)

# Tenta criar a tabela na inicialização (Render.com)
try:
    create_table()
except ConnectionError:
    print("Aguardando credenciais de conexão do PostgreSQL...")


# --- Rotas da Aplicação ---

@app.route('/')
def index():
    query = 'SELECT * FROM produtos ORDER BY id DESC'
    produtos = executar_query(query, fetch_mode='all')
    return render_template('index.html', produtos=produtos)

@app.route('/adicionar', methods=('GET', 'POST'))
def adicionar_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        categoria = request.form['categoria']
        
        try:
            quantidade = int(request.form['quantidade'])
            valor = float(request.form['valor'].replace(',', '.'))
        except ValueError:
            return render_template('adicionar.html', mensagem=("danger", "Erro: Quantidade e Valor devem ser números válidos.")), 400 
            
        codigo = gerar_proximo_codigo()
        data_cadastro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Conexão manual para garantir o ID retornado e registrar as duas ações em sequência
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # 1. Inserir produto e obter o ID (PostgreSQL RETURNING ID)
            query_insert_produto = "INSERT INTO produtos (codigo, nome, categoria, quantidade, valor_unitario, data_cadastro) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
            params_insert_produto = (codigo, nome, categoria, quantidade, valor, data_cadastro)
            cur.execute(query_insert_produto, params_insert_produto)
            produto_id = cur.fetchone()[0]
            
            # 2. Registrar MOVIMENTACAO de ENTRADA (Cadastro Inicial)
            query_insert_mov = "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_movimentacao) VALUES (%s, %s, %s, %s)"
            params_insert_mov = (produto_id, 'ENTRADA', quantidade, data_cadastro)
            cur.execute(query_insert_mov, params_insert_mov)

            conn.commit()

        except Exception as e:
            if conn: conn.rollback()
            print(f"Erro no cadastro e movimento: {e}")
            return render_template('adicionar.html', mensagem=("danger", "Erro: Falha ao cadastrar o produto e a movimentação.")), 500
        finally:
            if conn: conn.close()

        return redirect(url_for('index'))
        
    return render_template('adicionar.html')

@app.route('/retirada', methods=('GET', 'POST'))
def retirada():
    mensagem = None
    if request.method == 'POST':
        codigo = request.form['codigo'].strip().upper()
        try:
            quantidade_retirada = int(request.form['quantidade'])
        except ValueError:
            mensagem = ("danger", "Erro: A quantidade deve ser um número inteiro.")
            return render_template('retirada.html', mensagem=mensagem)

        query_select = 'SELECT id, quantidade, nome FROM produtos WHERE codigo = %s'
        produto = executar_query(query_select, (codigo,), fetch_mode='one')

        if produto is None:
            mensagem = ("danger", f"Erro: Produto com código '{codigo}' não encontrado no estoque.")
        elif quantidade_retirada <= 0:
            mensagem = ("warning", "A quantidade de retirada deve ser positiva.")
        elif quantidade_retirada > produto['quantidade']:
            mensagem = ("danger", f"Erro: Estoque insuficiente! Existem apenas {produto['quantidade']} unidades do produto {produto['nome']} (Código: {codigo}).")
        else:
            nova_quantidade = produto['quantidade'] - quantidade_retirada
            data_movimentacao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 1. Update PRODUTOS quantity
            query_update_produto = 'UPDATE produtos SET quantidade = %s WHERE codigo = %s'
            params_update = (nova_quantidade, codigo)
            executar_query(query_update_produto, params_update)

            # 2. Insert record into MOVIMENTACOES table
            query_insert_mov = "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_movimentacao) VALUES (%s, %s, %s, %s)"
            params_insert = (produto['id'], 'SAIDA', quantidade_retirada, data_movimentacao) 
            executar_query(query_insert_mov, params_insert)
            
            mensagem = ("success", f"Sucesso! Retirada de {quantidade_retirada} unidades de {produto['nome']} (Código: {codigo}) registrada. Novo estoque: {nova_quantidade}.")
    
    return render_template('retirada.html', mensagem=mensagem)

@app.route('/atualizar_estoque', methods=('GET', 'POST'))
def atualizar_estoque():
    mensagem = None
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        data_movimentacao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # --- Lógica de EXCLUSÃO ---
        if 'btn_excluir' in request.form:
            if not codigo:
                mensagem = ("danger", "Erro: O código do produto é obrigatório para a exclusão.")
            else:
                query_select = 'SELECT id, nome FROM produtos WHERE codigo = %s'
                produto = executar_query(query_select, (codigo,), fetch_mode='one')
                
                if produto is None:
                    mensagem = ("danger", f"Erro: Produto com código '{codigo}' não encontrado para exclusão.")
                else:
                    # 1. Remover MOVIMENTACOES (Regras de FOREIGN KEY)
                    query_delete_mov = 'DELETE FROM movimentacoes WHERE produto_id = %s'
                    executar_query(query_delete_mov, (produto['id'],))
                    
                    # 2. Remover PRODUTO
                    query_delete_prod = 'DELETE FROM produtos WHERE codigo = %s'
                    executar_query(query_delete_prod, (codigo,))
                    
                    mensagem = ("success", f"Sucesso! O produto '{produto['nome']}' (Código: {codigo}) foi EXCLUÍDO permanentemente do estoque e seu histórico removido.")
            
            return render_template('atualizar.html', mensagem=mensagem)
        
        # --- Lógica de AJUSTE/ATUALIZAÇÃO DE QUANTIDADE ---
        try:
            nova_quantidade = int(request.form.get('nova_quantidade', -1))
        except ValueError:
            mensagem = ("danger", "Erro: A nova quantidade deve ser um número inteiro.")
            return render_template('atualizar.html', mensagem=mensagem)

        query_select = 'SELECT id, quantidade, nome FROM produtos WHERE codigo = %s'
        produto = executar_query(query_select, (codigo,), fetch_mode='one')
        
        if produto is None:
            mensagem = ("danger", f"Erro: Produto com código '{codigo}' não encontrado.")
        elif nova_quantidade < 0:
            mensagem = ("danger", "Erro: A quantidade de estoque não pode ser negativa.")
        else:
            diferenca = nova_quantidade - produto['quantidade']
            
            if diferenca != 0:
                # 1. Update PRODUTOS quantity
                query_update_produto = 'UPDATE produtos SET quantidade = %s WHERE codigo = %s'
                params_update = (nova_quantidade, codigo)
                executar_query(query_update_produto, params_update)

                # 2. Insert record into MOVIMENTACOES table
                tipo_mov = 'AJUSTE_ENTRADA' if diferenca > 0 else 'AJUSTE_SAIDA'
                quantidade_mov = abs(diferenca)

                query_insert_mov = "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_movimentacao) VALUES (%s, %s, %s, %s)"
                params_insert = (produto['id'], tipo_mov, quantidade_mov, data_movimentacao) 
                executar_query(query_insert_mov, params_insert)

                if diferenca > 0:
                    tipo = "success"
                    msg = f"Sucesso! Estoque de {produto['nome']} ajustado (ENTRADA de {abs(diferenca)} unidades). Novo estoque: {nova_quantidade}."
                else:
                    tipo = "warning"
                    msg = f"Sucesso! Estoque de {produto['nome']} ajustado (SAÍDA/PERDA de {abs(diferenca)} unidades). Novo estoque: {nova_quantidade}."
            else:
                tipo = "info"
                msg = f"Nenhuma alteração feita em {produto['nome']}."
            
            mensagem = (tipo, msg)
            
    return render_template('atualizar.html', mensagem=mensagem)

@app.route('/amostragem')
def amostragem():
    query = 'SELECT * FROM produtos'
    produtos_pg = executar_query(query, fetch_mode='all')
    
    if not produtos_pg:
        return render_template('amostra.html', amostra_produtos=None, mensagem="Estoque vazio. Adicione produtos para realizar a amostragem.")

    # Converte a lista de dicionários para um DataFrame Pandas
    df = pd.DataFrame(produtos_pg)
    
    # Lógica de Amostragem Estratificada (10% por Categoria)
    try:
        def sample_group(group):
            n_sample = max(1, int(len(group) * 0.10)) 
            return group.sample(n=n_sample, random_state=42)
            
        amostra_df = df.groupby('categoria', group_keys=False).apply(sample_group).reset_index(drop=True)
        mensagem = f"Amostra Estratificada Gerada ({len(amostra_df)} itens) - 10% de cada categoria."
        
    except ValueError:
        amostra_df = df.sample(frac=0.1, random_state=42)
        mensagem = f"Amostra Simples Gerada ({len(amostra_df)} itens) - 10% do total."

    amostra_produtos = amostra_df.to_dict('records')
    
    return render_template('amostra.html', amostra_produtos=amostra_produtos, mensagem=mensagem)


if __name__ == '__main__':
    print("Servidor Flask LOCAL rodando na porta 5000...")
    app.run(debug=True, host='0.0.0.0', port=5000)