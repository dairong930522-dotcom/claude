#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Gestión de Expedientes - Despacho Breña
Aplicación Web Simple
"""

import sys
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import webbrowser
from threading import Timer

app = Flask(__name__)
DB_PATH = 'despacho.db'

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Despacho Breña - Sistema de Gestión</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2E75B6 0%, #1a4d7a 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 32px; margin-bottom: 10px; }
        .header p { font-size: 16px; opacity: 0.9; }
        .tabs {
            display: flex;
            background: #f5f5f5;
            border-bottom: 2px solid #ddd;
            overflow-x: auto;
        }
        .tab {
            padding: 15px 30px;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 16px;
            font-weight: 600;
            color: #666;
            transition: all 0.3s;
            white-space: nowrap;
        }
        .tab:hover { background: #e0e0e0; }
        .tab.active {
            background: white;
            color: #2E75B6;
            border-bottom: 3px solid #2E75B6;
        }
        .content { padding: 30px; }
        .tab-content { display: none; }
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .stat-card h3 { font-size: 14px; opacity: 0.9; margin-bottom: 10px; }
        .stat-card .number { font-size: 36px; font-weight: bold; }
        .btn {
            background: #2E75B6;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .btn:hover {
            background: #1a4d7a;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #218838; }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            margin-top: 20px;
        }
        th {
            background: #2E75B6;
            color: white;
            padding: 15px;
            text-align: left;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover { background: #f8f9fa; }
        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-danger { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Sistema de Gestión de Expedientes</h1>
            <p>Despacho Breña - Control Total en Tiempo Real</p>
        </div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
            <button class="tab" onclick="showTab('expedientes')">📁 Expedientes</button>
            <button class="tab" onclick="showTab('nuevo')">➕ Nuevo Expediente</button>
        </div>

        <div class="content">
            <div id="dashboard" class="tab-content active">
                <h2 style="margin-bottom: 20px;">Dashboard Principal</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>Total Expedientes</h3>
                        <div class="number" id="total-exp">0</div>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <h3>En Tramitación</h3>
                        <div class="number" id="en-tramite">0</div>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                        <h3>Favorables</h3>
                        <div class="number" id="favorables">0</div>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                        <h3>Este Mes</h3>
                        <div class="number" id="este-mes">0</div>
                    </div>
                </div>
                <table id="table-recientes">
                    <thead>
                        <tr>
                            <th>N° Exp</th>
                            <th>Cliente</th>
                            <th>Tipo</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div id="expedientes" class="tab-content">
                <h2 style="margin-bottom: 20px;">Todos los Expedientes</h2>
                <table id="table-expedientes">
                    <thead>
                        <tr>
                            <th>N° Exp</th>
                            <th>Cliente</th>
                            <th>NIE</th>
                            <th>Tipo</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div id="nuevo" class="tab-content">
                <h2 style="margin-bottom: 20px;">Nuevo Expediente</h2>
                <form id="form-expediente" onsubmit="guardarExpediente(event)">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div class="form-group">
                            <label>Número de Expediente *</label>
                            <input type="text" name="num_exp" required placeholder="EXP-2026-001">
                        </div>
                        <div class="form-group">
                            <label>Cliente *</label>
                            <input type="text" name="cliente" required>
                        </div>
                        <div class="form-group">
                            <label>NIE/Pasaporte *</label>
                            <input type="text" name="nie" required>
                        </div>
                        <div class="form-group">
                            <label>Tipo de Procedimiento *</label>
                            <select name="tipo_procedimiento" required>
                                <option value="">Seleccionar...</option>
                                <option>Arraigo Social</option>
                                <option>Arraigo Laboral</option>
                                <option>Residencia y Trabajo</option>
                                <option>Nacionalidad Española</option>
                                <option>Renovación</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Estado *</label>
                            <select name="estado" required>
                                <option value="">Seleccionar...</option>
                                <option>Pendiente</option>
                                <option>En tramitación</option>
                                <option>Favorable</option>
                                <option>Denegado</option>
                            </select>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-success">💾 Guardar Expediente</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');

            if (tabName === 'dashboard') cargarDashboard();
            if (tabName === 'expedientes') cargarExpedientes();
        }

        async function guardarExpediente(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);

            const response = await fetch('/api/expedientes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                alert('✅ Expediente guardado correctamente');
                e.target.reset();
                showTab('dashboard');
            }
        }

        async function cargarDashboard() {
            const response = await fetch('/api/stats');
            const stats = await response.json();

            document.getElementById('total-exp').textContent = stats.total || 0;
            document.getElementById('en-tramite').textContent = stats.en_tramitacion || 0;
            document.getElementById('favorables').textContent = stats.favorables || 0;
            document.getElementById('este-mes').textContent = stats.este_mes || 0;

            const expsResp = await fetch('/api/expedientes?limit=5');
            const exps = await expsResp.json();

            const tbody = document.querySelector('#table-recientes tbody');
            tbody.innerHTML = exps.map(exp => `
                <tr>
                    <td><strong>${exp.num_exp}</strong></td>
                    <td>${exp.cliente}</td>
                    <td>${exp.tipo_procedimiento}</td>
                    <td><span class="badge badge-${getBadgeClass(exp.estado)}">${exp.estado}</span></td>
                </tr>
            `).join('');
        }

        async function cargarExpedientes() {
            const response = await fetch('/api/expedientes');
            const exps = await response.json();

            const tbody = document.querySelector('#table-expedientes tbody');
            tbody.innerHTML = exps.map(exp => `
                <tr>
                    <td><strong>${exp.num_exp}</strong></td>
                    <td>${exp.cliente}</td>
                    <td>${exp.nie}</td>
                    <td>${exp.tipo_procedimiento}</td>
                    <td><span class="badge badge-${getBadgeClass(exp.estado)}">${exp.estado}</span></td>
                </tr>
            `).join('');
        }

        function getBadgeClass(estado) {
            if (estado === 'Favorable') return 'success';
            if (estado === 'Denegado') return 'danger';
            return 'warning';
        }

        cargarDashboard();
    </script>
</body>
</html>
'''

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS expedientes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  num_exp TEXT UNIQUE,
                  cliente TEXT,
                  nie TEXT,
                  tipo_procedimiento TEXT,
                  estado TEXT,
                  fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/expedientes', methods=['GET', 'POST'])
def expedientes():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        data = request.json
        try:
            c.execute('''INSERT INTO expedientes (num_exp, cliente, nie, tipo_procedimiento, estado)
                        VALUES (?, ?, ?, ?, ?)''',
                     (data.get('num_exp'), data.get('cliente'), data.get('nie'),
                      data.get('tipo_procedimiento'), data.get('estado')))
            conn.commit()
            return jsonify({'success': True}), 201
        except:
            return jsonify({'error': 'Error al guardar'}), 400
        finally:
            conn.close()
    else:
        limit = request.args.get('limit', type=int)
        query = 'SELECT * FROM expedientes ORDER BY id DESC'
        if limit:
            query += f' LIMIT {limit}'
        c.execute(query)
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify(rows)

@app.route('/api/stats')
def stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM expedientes')
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM expedientes WHERE estado = 'En tramitación'")
    en_tramitacion = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM expedientes WHERE estado = 'Favorable'")
    favorables = c.fetchone()[0]
    mes_actual = datetime.now().strftime('%Y-%m')
    c.execute(f"SELECT COUNT(*) FROM expedientes WHERE fecha_creacion LIKE '{mes_actual}%'")
    este_mes = c.fetchone()[0]
    conn.close()
    return jsonify({
        'total': total,
        'en_tramitacion': en_tramitacion,
        'favorables': favorables,
        'este_mes': este_mes
    })

def open_browser():
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SISTEMA DE GESTIÓN - DESPACHO BREÑA")
    print("="*60)
    print("\n✅ Iniciando aplicación...")
    init_db()
    print("✅ Base de datos lista")
    print("\n🌐 Abriendo navegador en: http://localhost:5000")
    print("\n⚠️  NO CIERRES ESTA VENTANA")
    print("   Para cerrar: presiona Ctrl+C")
    print("\n" + "="*60 + "\n")
    Timer(1.5, open_browser).start()
    app.run(debug=False, port=5000, host='127.0.0.1')
