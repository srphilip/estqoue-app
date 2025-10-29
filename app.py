from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import sqlite3
import pandas as pd
import io
from datetime import datetime

app = Flask(__name__)
DB_NAME = "inventory.db"

# ------------------ BANCO ------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS produtos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE,
                    nome TEXT,
                    categoria TEXT,
                    unidade TEXT,
                    fornecedor TEXT,
                    quantidade INTEGER
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimentacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produto_id INTEGER,
                    tipo TEXT,
                    quantidade INTEGER,
                    data TEXT,
                    FOREIGN KEY(produto_id) REFERENCES produtos(id)
                )''')
    conn.commit()
    conn.close()

def gerar_codigo():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM produtos")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"P{count:03d}"

# ------------------ ROTAS ------------------
@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM produtos")
    produtos = c.fetchall()
    conn.close()
    return render_template('index.html', produtos=produtos)

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        nome = request.form['nome']
        categoria = request.form['categoria']
        unidade = request.form['unidade']
        fornecedor = request.form['fornecedor']
        quantidade = int(request.form['quantidade'])
        codigo = gerar_codigo()

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO produtos (codigo, nome, categoria, unidade, fornecedor, quantidade) VALUES (?, ?, ?, ?, ?, ?)",
                  (codigo, nome, categoria, unidade, fornecedor, quantidade))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('add_product.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == 'POST':
        nome = request.form['nome']
        categoria = request.form['categoria']
        unidade = request.form['unidade']
        fornecedor = request.form['fornecedor']
        quantidade = int(request.form['quantidade'])
        c.execute("UPDATE produtos SET nome=?, categoria=?, unidade=?, fornecedor=?, quantidade=? WHERE id=?",
                  (nome, categoria, unidade, fornecedor, quantidade, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    c.execute("SELECT * FROM produtos WHERE id=?", (id,))
    produto = c.fetchone()
    conn.close()
    return render_template('edit_product.html', produto=produto)

@app.route('/delete/<int:id>')
def delete_product(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM produtos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/movimentacao', methods=['GET', 'POST'])
def movimentacao():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'POST':
        produto_id = int(request.form['produto'])
        tipo = request.form['tipo']
        quantidade = int(request.form['quantidade'])
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Atualiza estoque
        if tipo == 'saida':
            c.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id=?", (quantidade, produto_id))
        else:
            c.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id=?", (quantidade, produto_id))

        # Registra movimentação
        c.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade, data) VALUES (?, ?, ?, ?)",
                  (produto_id, tipo, quantidade, data))
        conn.commit()
        conn.close()
        return redirect(url_for('movimentacao'))

    c.execute("SELECT id, nome FROM produtos")
    produtos = c.fetchall()
    conn.close()
    return render_template('movimentacao.html', produtos=produtos)

@app.route('/relatorios')
def relatorios():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT m.id, p.nome, m.tipo, m.quantidade, m.data
                 FROM movimentacoes m
                 JOIN produtos p ON p.id = m.produto_id
                 ORDER BY m.data DESC''')
    dados = c.fetchall()
    conn.close()
    return render_template('relatorios.html', dados=dados)

@app.route('/exportar')
def exportar():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM produtos", conn)
    conn.close()
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype='text/csv', download_name='estoque.csv', as_attachment=True)

# ------------------ API ------------------
@app.route('/api/produtos')
def api_produtos():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM produtos", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
