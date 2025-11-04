# app.py (Código Final para Execução Local com SQLite)

from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from datetime import datetime
import os
import random
import sqlite3 
import io
import base64

# Importar bibliotecas de visualização
import matplotlib
matplotlib.use('Agg') # Necessário para rodar Matplotlib em ambientes sem GUI
import matplotlib.pyplot as plt
import seaborn as sns

# --- CONFIGURAÇÃO DE BANCO DE DADOS LOCAL ---
# O arquivo database.db será criado nesta mesma pasta
DB_NAME = 'database.db' 
app = Flask(__name__) 

# --- Funções de Banco de Dados ---

def get_db_connection():
    """Conecta ao banco de dados SQLite."""
    conn = sqlite3.connect(DB_NAME)
    # Define o row_factory para acessar colunas por nome (como um dicionário)
    conn.row_factory = sqlite3.Row
    return conn

def executar_query(query, params=None, fetch_mode='none'):
    """Função centralizada para executar comandos e queries no SQLite."""
    conn = None
    resultado = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch_mode == 'one':
            resultado = cur.fetchone()
        elif fetch_mode == 'all':
            resultado = cur.fetchall()
        
        conn.commit()
        cur.close()
        
        # Converte sqlite3.Row para dicionário padrão para uso consistente
        if fetch_mode == 'all' and resultado:
            resultado = [dict(row) for row in resultado]
        if fetch_mode == 'one' and resultado:
            resultado = dict(resultado)
            
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
    """Gera o próximo código sequencial (P001, P002...) no SQLite."""
    query = 'SELECT MAX(id) FROM produtos'
    resultado = executar_query(query, fetch_mode='one') 
    
    last_id = resultado['MAX(id)'] if resultado and resultado['MAX(id)'] is not None else 0 
    
    next_id = last_id + 1
    return f'P{next_id:03d}' 

def create_table():
    """Cria as tabelas de produtos e movimentações no SQLite."""
    # Tabela PRODUTOS (com os novos campos)
    query_produtos = '''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,  
            nome TEXT NOT NULL,
            categoria TEXT,
            unidade_medida TEXT, 
            marca TEXT,          
            fornecedor TEXT,     
            quantidade INTEGER NOT NULL,
            valor_unitario REAL,
            data_cadastro TEXT
        );
    '''
    executar_query(query_produtos)
    
    # Tabela MOVIMENTACOES (para auditoria)
    query_movimentacoes = '''
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER, 
            tipo TEXT NOT NULL, 
            quantidade INTEGER NOT NULL,
            data_movimentacao TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );
    '''
    executar_query(query_movimentacoes)

# Inicializa o banco de dados e as tabelas
create_table()


# --- Funções de Gráficos ---

def gerar_grafico(df, tipo, titulo, xlabel="", ylabel=""):
    """Gera um gráfico do tipo Barra, Rosca ou dispersão."""
    plt.figure(figsize=(10, 6))
    
    if df.empty:
        return None
        
    if tipo == 'barra_qtd_categoria':
        # Gráfico de barras da quantidade total por categoria
        data = df.groupby('categoria')['quantidade'].sum().sort_values(ascending=False)
        sns.barplot(x=data.index, y=data.values, palette='viridis')
        plt.xticks(rotation=45, ha='right')
    
    elif tipo == 'barra_produtos_valor':
        # Top 10 produtos por valor total (quantidade * valor_unitario)
        df['valor_total'] = df['quantidade'] * df['valor_unitario']
        data = df.nlargest(10, 'valor_total')
        sns.barplot(x='nome', y='valor_total', data=data, palette='magma')
        plt.xticks(rotation=45, ha='right')
        
    elif tipo == 'rosca_categorias':
        # Gráfico de rosca para proporção de produtos (COUNT) por categoria
        data = df['categoria'].value_counts()
        plt.pie(data, labels=data.index, autopct='%1.1f%%', startangle=90, wedgeprops=dict(width=0.4), pctdistance=0.75)
        plt.title(titulo, y=1.08)
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(axis='y', linestyle='--')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close() 
    
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# --- Rotas da Aplicação ---

@app.route('/')
def index():
    query = 'SELECT * FROM produtos ORDER BY id DESC'
    produtos = executar_query(query, fetch_mode='all')
    return render_template('index.html', produtos=produtos)

@app.route('/graficos')
def graficos():
    query = 'SELECT nome, categoria, quantidade, valor_unitario FROM produtos WHERE quantidade > 0'
    produtos = executar_query(query, fetch_mode='all')
    
    if not produtos:
        return render_template('graficos.html', mensagem="Estoque vazio. Adicione produtos para gerar relatórios.")
        
    df = pd.DataFrame(produtos)
    
    grafico1 = gerar_grafico(df, 
        tipo='barra_qtd_categoria', 
        titulo='Estoque Total por Categoria (Unidades)', 
        xlabel='Categoria', 
        ylabel='Soma das Unidades em Estoque'
    )
    
    grafico2 = gerar_grafico(df, 
        tipo='barra_produtos_valor', 
        titulo='Top 10 Produtos por Valor Total (R$)', 
        xlabel='Produto', 
        ylabel='Valor Total no Estoque (R$)'
    )
    
    grafico3 = gerar_grafico(df, 
        tipo='rosca_categorias', 
        titulo='Proporção de Itens por Categoria (Contagem)'
    )
    
    return render_template('graficos.html', grafico1=grafico1, grafico2=grafico2, grafico3=grafico3)

@app.route('/adicionar', methods=('GET', 'POST'))
def adicionar_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        categoria = request.form['categoria']
        unidade_medida = request.form['unidade_medida'] 
        marca = request.form['marca']                   
        fornecedor = request.form['fornecedor']         
        
        try:
            quantidade = int(request.form['quantidade'])
            valor = float(request.form['valor'].replace(',', '.'))
        except ValueError:
            return render_template('adicionar.html', mensagem=("danger", "Erro: Quantidade e Valor devem ser números válidos.")), 400 
            
        codigo = gerar_proximo_codigo()
        data_cadastro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = None
        try:
            # Usamos a conexão manual para obter o 'lastrowid' (SQLite)
            conn = get_db_connection()
            cur = conn.cursor()

            query_insert_produto = "INSERT INTO produtos (codigo, nome, categoria, unidade_medida, marca, fornecedor, quantidade, valor_unitario, data_cadastro) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            params_insert_produto = (codigo, nome, categoria, unidade_medida, marca, fornecedor, quantidade, valor, data_cadastro) 
            
            cur.execute(query_insert_produto, params_insert_produto)
            produto_id = cur.lastrowid # SQLite retorna o ID assim
            
            # 2. Registrar MOVIMENTACAO de ENTRADA 
            query_insert_mov = "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_movimentacao) VALUES (?, ?, ?, ?)"
            params_insert_mov = (produto_id, 'ENTRADA', quantidade, data_cadastro)
            cur.execute(query_insert_mov, params_insert_mov)

            conn.commit()
            cur.close()

        except Exception as e:
            if conn: conn.rollback()
            print(f"Erro no cadastro e movimento: {e}")
            return render_template('adicionar.html', mensagem=("danger", "Falha ao cadastrar o produto e a movimentação.")), 500
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

        # Usamos '?' para placeholders no SQLite
        query_select = 'SELECT id, quantidade, nome FROM produtos WHERE codigo = ?'
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

            # 1. Update PRODUTOS
            query_update_produto = 'UPDATE produtos SET quantidade = ? WHERE codigo = ?'
            params_update = (nova_quantidade, codigo)
            executar_query(query_update_produto, params_update)

            # 2. Insert MOVIMENTACOES
            query_insert_mov = "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_movimentacao) VALUES (?, ?, ?, ?)"
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
                query_select = 'SELECT id, nome FROM produtos WHERE codigo = ?'
                produto = executar_query(query_select, (codigo,), fetch_mode='one')
                
                if produto is None:
                    mensagem = ("danger", f"Erro: Produto com código '{codigo}' não encontrado para exclusão.")
                else:
                    # 1. Remover MOVIMENTACOES (Regras de FOREIGN KEY)
                    query_delete_mov = 'DELETE FROM movimentacoes WHERE produto_id = ?'
                    executar_query(query_delete_mov, (produto['id'],))
                    
                    # 2. Remover PRODUTO
                    query_delete_prod = 'DELETE FROM produtos WHERE codigo = ?'
                    executar_query(query_delete_prod, (codigo,))
                    
                    mensagem = ("success", f"Sucesso! O produto '{produto['nome']}' (Código: {codigo}) foi EXCLUÍDO permanentemente do estoque e seu histórico removido.")
            
            return render_template('atualizar.html', mensagem=mensagem)
        
        # --- Lógica de AJUSTE/ATUALIZAÇÃO DE QUANTIDADE ---
        try:
            nova_quantidade = int(request.form.get('nova_quantidade', -1))
        except ValueError:
            mensagem = ("danger", "Erro: A nova quantidade deve ser um número inteiro.")
            return render_template('atualizar.html', mensagem=mensagem)

        query_select = 'SELECT id, quantidade, nome FROM produtos WHERE codigo = ?'
        produto = executar_query(query_select, (codigo,), fetch_mode='one')
        
        if produto is None:
            mensagem = ("danger", f"Erro: Produto com código '{codigo}' não encontrado.")
        elif nova_quantidade < 0:
            mensagem = ("danger", "Erro: A quantidade de estoque não pode ser negativa.")
        else:
            diferenca = nova_quantidade - produto['quantidade']
            
            if diferenca != 0:
                # 1. Update PRODUTOS
                query_update_produto = 'UPDATE produtos SET quantidade = ? WHERE codigo = ?'
                params_update = (nova_quantidade, codigo)
                executar_query(query_update_produto, params_update)

                # 2. Insert MOVIMENTACOES
                tipo_mov = 'AJUSTE_ENTRADA' if diferenca > 0 else 'AJUSTE_SAIDA'
                quantidade_mov = abs(diferenca)

                query_insert_mov = "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_movimentacao) VALUES (?, ?, ?, ?)"
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
    produtos_sql = executar_query(query, fetch_mode='all')
    
    if not produtos_sql:
        return render_template('amostra.html', amostra_produtos=None, mensagem="Estoque vazio. Adicione produtos para realizar a amostragem.")

    df = pd.DataFrame(produtos_sql)
    
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


# --- Execução Local ---
if __name__ == '__main__':
    print("=======================================================")
    print("  ✅ SISTEMA DE ESTOQUE LOCAL (COM GRÁFICOS)!")
    print("  Acesse no navegador: http://127.0.0.1:5000/")
    print("  Para acesso na rede: http://IP_DO_SEU_PC:5000/")
    print("=======================================================")
    # host='0.0.0.0' permite que outros computadores na rede acessem
    app.run(debug=True, host='0.0.0.0', port=5000)