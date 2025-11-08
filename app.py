import csv
import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
import locale
import urllib.parse
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
import json

# --- Configuração ---
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    print("Locale 'pt_BR.UTF-8' não encontrado. Usando locale padrão.")

app = Flask(__name__)
# --- CORREÇÃO DE CORS (para Render/Netlify) ---
origins = [
    "https://guia-kaibora.netlify.app", # O seu site Netlify
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5501",
    "null" # Para testes locais (abrir o ficheiro diretamente)
]
CORS(app, origins=origins, supports_credentials=True)

base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'kaibora.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "SUA-CHAVE-SECRETA-MUITO-FORTE" 
jwt = JWTManager(app)
db = SQLAlchemy(app)

# --- DADOS EM MEMÓRIA (Temporários) ---
ALERTAS_DB = [] 

# --- MODELOS DE BANCO DE DADOS ---
class Aventureiro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nome_aventureiro = db.Column(db.String(100), unique=True, nullable=False)
    nome_jogador = db.Column(db.String(100), nullable=True)
    classe_origem = db.Column(db.String(100), nullable=True)
    motivacao = db.Column(db.Text, nullable=True)
    xp = db.Column(db.Integer, default=0)
    kaicons = db.Column(db.Integer, default=50)
    nivel = db.Column(db.Integer, default=1)
    habilidades = db.Column(db.Text, nullable=True, default='')
    backup_arquivos = db.Column(db.Text, nullable=True, default='{}') 
    inventario = db.Column(db.Text, nullable=True, default='{}')
    localizacao_atual = db.Column(db.String(100), nullable=True, default='Desconhecido')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def to_dict(self):
        return {
            "id": self.id, "username": self.username, "nome_aventureiro": self.nome_aventureiro,
            "nome_jogador": self.nome_jogador, "classe_origem": self.classe_origem,
            "motivacao": self.motivacao, "xp": self.xp, "kaicons": self.kaicons,
            "nivel": self.nivel, "habilidades": self.habilidades,
            "backup_arquivos": self.backup_arquivos, "inventario": self.inventario,
            "localizacao_atual": self.localizacao_atual
        }
class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(200), nullable=False)
    xp_reward = db.Column(db.Integer, default=10)
    kc_reward = db.Column(db.Integer, default=5)
    def to_dict(self):
        return {"id": self.id, "texto": self.texto, "xp_reward": self.xp_reward, "kc_reward": self.kc_reward}
class Cronograma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora = db.Column(db.Integer, nullable=False)
    minuto = db.Column(db.Integer, nullable=False)
    texto = db.Column(db.String(200), nullable=False)
    def to_dict(self): return {"id": self.id, "hora": self.hora, "minuto": self.minuto, "texto": self.texto}
class Rodizio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_tarefa = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(250), nullable=False)
    def to_dict(self): return {"id": self.id, "nome_tarefa": self.nome_tarefa, "descricao": self.descricao}
class RegistroInformes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    texto = db.Column(db.String(500), nullable=False)
    def to_dict(self):
        return {"id": self.id, "timestamp": self.timestamp.strftime("%d/%m %H:%M"), "texto": self.texto}
class ChatMensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    nome_autor = db.Column(db.String(100), nullable=False)
    texto = db.Column(db.String(500), nullable=False)
    def to_dict(self):
        return {"id": self.id, "timestamp": self.timestamp.strftime("%H:%M"), "nome_autor": self.nome_autor, "texto": self.texto}
class LojaItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    preco = db.Column(db.Integer, nullable=False)
    estoque = db.Column(db.Integer, default=0)
    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "descricao": self.descricao, "preco": self.preco, "estoque": self.estoque}
class HabitatSistema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    setor = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='FUNCIONAL')
    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "setor": self.setor, "status": self.status}
class EsbocoMapa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    nome_autor = db.Column(db.String(100), nullable=False)
    nome_setor = db.Column(db.String(100), nullable=False)
    notas = db.Column(db.Text, nullable=True)
    def to_dict(self):
        return {
            "id": self.id, "timestamp": self.timestamp.strftime("%d/%m %H:%M"),
            "nome_autor": self.nome_autor, "nome_setor": self.nome_setor, "notas": self.notas
        }
class NPC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    localizacao_atual = db.Column(db.String(100), nullable=True, default='Germinal')
    def to_dict(self):
        return {
            "id": self.id, "nome": self.nome, "descricao": self.descricao,
            "localizacao_atual": self.localizacao_atual
        }
# --- NOVO MODELO: PRODUÇÃO (Crafting) ---
class Receita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_item_final = db.Column(db.String(100), nullable=False)
    quantia_produzida = db.Column(db.Integer, nullable=False, default=1)
    ingredientes_json = db.Column(db.Text, nullable=False, default='{}')
    def to_dict(self):
        return {
            "id": self.id, "nome_item_final": self.nome_item_final,
            "quantia_produzida": self.quantia_produzida,
            "ingredientes_json": self.ingredientes_json
        }

# --- FUNÇÕES HELPER ---
def get_lista_nomes_jogadores():
    try:
        aventureiros = Aventureiro.query.all()
        return [a.nome_aventureiro for a in aventureiros]
    except Exception as e:
        print(f"Erro ao buscar jogadores do DB: {e}")
        return []
def calcular_atribuicao(dia, jogadores, tarefas):
    if not jogadores or not tarefas: return []
    dia_do_ano = dia.timetuple().tm_yday
    num_jogadores = len(jogadores)
    atribuicoes = []
    for i, tarefa in enumerate(tarefas):
        jogador_index = (dia_do_ano + i) % num_jogadores
        jogador_designado = jogadores[jogador_index]
        atribuicoes.append({
            "id_tarefa": tarefa.id, "nome_tarefa": tarefa.nome_tarefa,
            "descricao": tarefa.descricao, "atribuido_a": jogador_designado
        })
    return atribuicoes
def adicionar_informe(texto):
    try:
        novo_informe = RegistroInformes(texto=texto)
        db.session.add(novo_informe)
        db.session.commit()
    except Exception as e:
        print(f"Erro ao adicionar informe ao log: {e}")
        db.session.rollback()
def calcular_xp_necessario(nivel):
    return nivel * 100
def verificar_level_up(aventureiro):
    xp_necessario = calcular_xp_necessario(aventureiro.nivel)
    upou = False
    while aventureiro.xp >= xp_necessario:
        aventureiro.xp -= xp_necessario
        aventureiro.nivel += 1
        upou = True
        log_msg = f"[NÍVEL] {aventureiro.nome_aventureiro} avançou para o Nível {aventureiro.nivel}!"
        adicionar_informe(log_msg)
        print(log_msg)
        xp_necessario = calcular_xp_necessario(aventureiro.nivel)
    return upou
def adicionar_alerta_global(texto):
    global ALERTAS_DB
    ALERTAS_DB.insert(0, texto)
    if len(ALERTAS_DB) > 5:
        ALERTAS_DB.pop()

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username'); password = data.get('password'); nome_aventureiro = data.get('nome_aventureiro')
    if not username or not password or not nome_aventureiro:
        return jsonify({"erro": "Usuário, senha e nome do aventureiro são obrigatórios."}), 400
    if Aventureiro.query.filter_by(username=username).first():
        return jsonify({"erro": "Este nome de usuário (login) já existe."}), 400
    if Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first():
        return jsonify({"erro": "Este nome de aventureiro (personagem) já existe."}), 400
    novo_aventureiro = Aventureiro(
        username=username, nome_aventureiro=nome_aventureiro,
        nome_jogador=data.get('nome_jogador', ''),
        classe_origem=data.get('classe_origem', ''),
        motivacao=data.get('motivacao', ''),
        localizacao_atual='Setor 1 (Germinal)'
    )
    novo_aventureiro.set_password(password)
    db.session.add(novo_aventureiro); db.session.commit()
    adicionar_informe(f"Aventureiro '{nome_aventureiro}' (Lvl 1) juntou-se ao Habitat.")
    return jsonify({"message": "Aventureiro registrado com sucesso! Você pode fazer login."}), 201
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username'); password = data.get('password')
    aventureiro = Aventureiro.query.filter_by(username=username).first()
    if not aventureiro or not aventureiro.check_password(password):
        return jsonify({"erro": "Login ou senha inválidos"}), 401
    access_token = create_access_token(identity=aventureiro.nome_aventureiro)
    return jsonify(access_token=access_token)

# --- ROTAS DO APP DO JOGADOR (kaibora.html) ---
@app.route('/api/tarefas', methods=['GET'])
@jwt_required()
def get_tarefas(): return jsonify([tarefa.to_dict() for tarefa in Tarefa.query.all()])
@app.route('/api/alertas', methods=['GET'])
@jwt_required()
def get_alertas(): return jsonify(ALERTAS_DB)
@app.route('/api/cronogramas', methods=['GET'])
@jwt_required()
def get_cronogramas(): return jsonify([crono.to_dict() for crono in Cronograma.query.order_by(Cronograma.hora, Cronograma.minuto).all()])
@app.route('/api/time', methods=['GET'])
@jwt_required()
def get_time():
    agora = datetime.now()
    return jsonify({"data": agora.strftime("%d/%m"), "hora": agora.hour, "minuto": agora.minute})
@app.route('/api/status/eventos', methods=['GET'])
@jwt_required()
def get_current_events():
    agora = datetime.now()
    eventos_db = Cronograma.query.filter_by(hora=agora.hour, minuto=agora.minute).all()
    return jsonify([evento.texto for evento in eventos_db])
@app.route('/api/rodizio/meu-horario', methods=['GET'])
@jwt_required()
def get_meu_rodizio_horario():
    nome_aventureiro = get_jwt_identity()
    jogadores = get_lista_nomes_jogadores()
    if not jogadores: return jsonify({"hoje": [], "amanha": []})
    tarefas = Rodizio.query.order_by(Rodizio.id).all()
    hoje_date = datetime.now().date()
    amanha_date = hoje_date + timedelta(days=1)
    atribuicoes_hoje = calcular_atribuicao(hoje_date, jogadores, tarefas)
    atribuicoes_amanha = calcular_atribuicao(amanha_date, jogadores, tarefas)
    minhas_tarefas_hoje = [t for t in atribuicoes_hoje if t['atribuido_a'] == nome_aventureiro]
    minhas_tarefas_amanha = [t for t in atribuicoes_amanha if t['atribuido_a'] == nome_aventureiro]
    dia_semana_hoje = hoje_date.strftime('%A').capitalize()
    dia_semana_amanha = amanha_date.strftime('%A').capitalize()
    return jsonify({
        "hoje": {"dia_semana": dia_semana_hoje, "tarefas": minhas_tarefas_hoje},
        "amanha": {"dia_semana": dia_semana_amanha, "tarefas": minhas_tarefas_amanha}
    })
@app.route('/api/aventureiro/status', methods=['GET'])
@jwt_required()
def get_aventureiro_status():
    nome_aventureiro = get_jwt_identity()
    aventureiro = Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first_or_404()
    return jsonify(aventureiro.to_dict())
@app.route('/api/informes', methods=['GET'])
@jwt_required()
def get_informes():
    informes_db = RegistroInformes.query.order_by(RegistroInformes.timestamp.desc()).limit(20).all()
    return jsonify([informe.to_dict() for informe in informes_db])
@app.route('/api/aventureiros/lista', methods=['GET'])
@jwt_required()
def get_lista_aventureiros_ativos():
    nome_logado = get_jwt_identity()
    aventureiros = Aventureiro.query.filter(Aventureiro.nome_aventureiro != nome_logado).all()
    nomes = [a.nome_aventureiro for a in aventureiros]
    return jsonify(nomes)
@app.route('/api/transferir', methods=['POST'])
@jwt_required()
def transferir_kaicons():
    nome_remetente = get_jwt_identity()
    remetente = Aventureiro.query.filter_by(nome_aventureiro=nome_remetente).first_or_404()
    data = request.json
    nome_destinatario = data.get('destinatario')
    try: quantia = int(data.get('quantia'))
    except (ValueError, TypeError): return jsonify({"erro": "Quantia inválida."}), 400
    if not nome_destinatario or quantia <= 0: return jsonify({"erro": "Destinatário ou quantia inválidos."}), 400
    destinatario = Aventureiro.query.filter_by(nome_aventureiro=nome_destinatario).first()
    if not destinatario: return jsonify({"erro": f"Aventureiro '{nome_destinatario}' não encontrado."}), 404
    if remetente.kaicons < quantia: return jsonify({"erro": "Kaicons insuficientes para esta troca."}), 400
    try:
        remetente.kaicons -= quantia
        destinatario.kaicons += quantia
        db.session.commit()
        return jsonify({"message": "Transferência concluída com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Uma falha interna impediu a troca."}), 500
@app.route('/api/chat', methods=['GET'])
@jwt_required()
def get_chat_mensagens():
    mensagens = ChatMensagem.query.order_by(ChatMensagem.timestamp.desc()).limit(50).all()
    mensagens.reverse()
    return jsonify([msg.to_dict() for msg in mensagens])
@app.route('/api/chat', methods=['POST'])
@jwt_required()
def post_chat_mensagem():
    nome_autor = get_jwt_identity()
    texto = request.json.get('texto')
    if not texto: return jsonify({"erro": "A mensagem não pode estar vazia."}), 400
    try:
        nova_mensagem = ChatMensagem(nome_autor=nome_autor, texto=texto)
        db.session.add(nova_mensagem); db.session.commit()
        return jsonify(nova_mensagem.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/aventureiro/backup', methods=['POST'])
@jwt_required()
def backup_arquivos():
    nome_aventureiro = get_jwt_identity()
    aventureiro = Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first_or_404()
    backup_data_string = request.json.get('backup_data')
    if backup_data_string is None:
        return jsonify({"erro": "Nenhum dado de backup enviado."}), 400
    try:
        aventureiro.backup_arquivos = backup_data_string
        db.session.commit()
        adicionar_informe(f"BKP do Kaipora de '{nome_aventureiro}' sincronizado com o Germinal.")
        return jsonify({"message": "Backup concluído com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/loja-itens', methods=['GET'])
@jwt_required() 
def get_loja_itens_jogador():
    itens = LojaItem.query.order_by(LojaItem.nome).all()
    return jsonify([item.to_dict() for item in itens])
@app.route('/api/loja/comprar/<int:id>', methods=['POST'])
@jwt_required()
def comprar_item_loja(id):
    nome_comprador = get_jwt_identity()
    comprador = Aventureiro.query.filter_by(nome_aventureiro=nome_comprador).first_or_404()
    item = LojaItem.query.get(id)
    if not item:
        return jsonify({"erro": "Item não encontrado na loja."}), 404
    if item.estoque <= 0:
        return jsonify({"erro": "Item fora de estoque."}), 400
    if comprador.kaicons < item.preco:
        return jsonify({"erro": "Kaicons insuficientes."}), 400
    try:
        comprador.kaicons -= item.preco
        item.estoque -= 1
        try:
            inventario = json.loads(comprador.inventario)
        except json.JSONDecodeError:
            inventario = {}
        item_nome_norm = item.nome.strip().lower()
        quantia_atual = inventario.get(item_nome_norm, 0)
        inventario[item_nome_norm] = quantia_atual + 1
        comprador.inventario = json.dumps(inventario)
        adicionar_informe(f"[LOJA] {comprador.nome_aventureiro} comprou '{item.nome}' por {item.preco} KÇ.")
        db.session.commit()
        return jsonify(comprador.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/mapa/esbocos', methods=['GET'])
def get_esbocos():
    esbocos_db = EsbocoMapa.query.order_by(EsbocoMapa.timestamp.desc()).limit(20).all()
    return jsonify([e.to_dict() for e in esbocos_db])
@app.route('/api/mapa/esboco', methods=['POST'])
@jwt_required()
def submit_esboco():
    nome_autor = get_jwt_identity()
    data = request.json
    nome_setor = data.get('nome_setor')
    notas = data.get('notas')
    if not nome_setor:
        return jsonify({"erro": "Nome do setor é obrigatório."}), 400
    try:
        novo_esboco = EsbocoMapa(nome_autor=nome_autor, nome_setor=nome_setor, notas=notas)
        db.session.add(novo_esboco)
        adicionar_informe(f"[MAPEAMENTO] {nome_autor} enviou um novo esboço 2D para o {nome_setor}.")
        db.session.commit()
        return jsonify(novo_esboco.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/aventureiro/localizacao', methods=['POST'])
@jwt_required()
def set_localizacao():
    nome_aventureiro = get_jwt_identity()
    aventureiro = Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first_or_404()
    local = request.json.get('localizacao')
    if not local:
        return jsonify({"erro": "Localização não fornecida."}), 400
    try:
        aventureiro.localizacao_atual = local
        db.session.commit()
        return jsonify({"message": f"Localização atualizada para {local}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
        
# --- ROTAS DE PRODUÇÃO (JOGADOR) ---
@app.route('/api/receitas', methods=['GET'])
@jwt_required()
def get_receitas_jogador():
    receitas = Receita.query.order_by(Receita.nome_item_final).all()
    return jsonify([r.to_dict() for r in receitas])

@app.route('/api/produzir/<int:id_receita>', methods=['POST'])
@jwt_required()
def produzir_item(id_receita):
    # 1. Identifica o jogador e a receita
    nome_jogador = get_jwt_identity()
    jogador = Aventureiro.query.filter_by(nome_aventureiro=nome_jogador).first_or_404()
    receita = Receita.query.get(id_receita)
    if not receita:
        return jsonify({"erro": "Receita não encontrada."}), 404
        
    try:
        # 2. Carrega o inventário do jogador e os ingredientes da receita
        inventario = json.loads(jogador.inventario)
        ingredientes = json.loads(receita.ingredientes_json)
        
        # 3. Verifica se o jogador tem os materiais
        for item, quantia_necessaria in ingredientes.items():
            item_norm = item.strip().lower() # Garante a normalização
            quantia_no_inventario = inventario.get(item_norm, 0)
            
            if quantia_no_inventario < quantia_necessaria:
                return jsonify({"erro": f"Materiais insuficientes. Falta: {item_norm} (x{quantia_necessaria - quantia_no_inventario})."}), 400
        
        # 4. Se tiver, consome os materiais
        for item, quantia_necessaria in ingredientes.items():
            item_norm = item.strip().lower()
            inventario[item_norm] -= quantia_necessaria
            if inventario[item_norm] == 0:
                del inventario[item_norm]
                
        # 5. Adiciona o item final
        item_final_norm = receita.nome_item_final.strip().lower()
        quantia_atual_final = inventario.get(item_final_norm, 0)
        inventario[item_final_norm] = quantia_atual_final + receita.quantia_produzida
        
        # 6. Salva o inventário de volta no DB
        jogador.inventario = json.dumps(inventario)
        
        # 7. Adiciona ao Log
        adicionar_informe(f"[OFICINA] {jogador.nome_aventureiro} produziu {receita.quantia_produzida}x '{item_final_norm}'.")
        
        db.session.commit()
        
        return jsonify(jogador.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500


# --- ROTAS DO TERMINAL DO GM ---
@app.route('/gm')
def gm_dashboard():
    try: return render_template('gm.html')
    except Exception as e: return f"Erro: 'gm.html' não encontrado. {e}", 404
@app.route('/gm-hub')
def gm_hub_dashboard():
    try: return render_template('gm_hub.html')
    except Exception as e: return f"Erro: 'gm_hub.html' não encontrado. {e}", 404
@app.route('/gm-loja')
def gm_loja_dashboard():
    try: return render_template('gm_loja.html')
    except Exception as e: return f"Erro: 'gm_loja.html' não encontrado. {e}", 404
@app.route('/gm-mapa')
def gm_mapa_dashboard():
    try: return render_template('gm_mapa.html')
    except Exception as e: return f"Erro: 'gm_mapa.html' não encontrado. {e}", 404
    
# --- NOVA ROTA: Hub da Oficina (GM) ---
@app.route('/gm-oficina')
def gm_oficina_dashboard():
    try: 
        return render_template('gm_oficina.html') # Serve o novo arquivo
    except Exception as e: 
        return f"Erro: 'gm_oficina.html' não encontrado. {e}", 404

@app.route('/api/jogadores', methods=['GET'])
def get_jogadores():
    aventureiros = Aventureiro.query.order_by(Aventureiro.nome_aventureiro).all()
    return jsonify([a.to_dict() for a in aventureiros])
@app.route('/api/jogadores/<nome>', methods=['DELETE'])
def delete_jogador(nome):
    try:
        nome_jogador = urllib.parse.unquote(nome)
        aventureiro_db = Aventureiro.query.filter_by(nome_aventureiro=nome_jogador).first()
        if aventureiro_db:
            db.session.delete(aventureiro_db)
            db.session.commit()
            adicionar_informe(f"Aventureiro '{nome_jogador}' foi removido do Habitat.")
            return jsonify({"message": f"Jogador {nome_jogador} removido com sucesso."}), 200
        else:
            return jsonify({"erro": "Jogador não encontrado no DB"}), 404
    except Exception as e:
        print(f"Erro ao deletar jogador: {e}")
        return jsonify({"erro": str(e)}), 500

# --- GERENCIAMENTO DE TAREFAS (Quests) ---
@app.route('/api/tarefas', methods=['POST'])
def add_tarefa():
    try:
        data = request.json
        if not data or 'texto' not in data: return jsonify({"erro": "Texto da tarefa é obrigatório"}), 400
        nova_tarefa = Tarefa(texto=data['texto'], xp_reward=data.get('xp_reward', 10), kc_reward=data.get('kc_reward', 5))
        db.session.add(nova_tarefa); db.session.commit()
        adicionar_informe(f"Nova Tarefa (Quest) adicionada: {nova_tarefa.texto}")
        return jsonify(nova_tarefa.to_dict()), 201
    except Exception as e: return jsonify({"erro": str(e)}), 500
@app.route('/api/tarefas/<int:id>', methods=['DELETE'])
def delete_tarefa_simples(id):
    tarefa = Tarefa.query.get(id)
    if tarefa:
        db.session.delete(tarefa); db.session.commit()
        return jsonify({"message": "Tarefa removida"}), 200
    return jsonify({"erro": "Tarefa não encontrada"}), 404
@app.route('/api/tarefas/<int:id>/complete', methods=['POST'])
def complete_tarefa(id):
    try:
        data = request.json
        nome_aventureiro = data.get('aventureiro_nome')
        if not nome_aventureiro: return jsonify({"erro": "Nome do aventureiro é obrigatório"}), 400
        aventureiro = Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first_or_404()
        tarefa = Tarefa.query.get_or_404(id)
        
        xp_ganho = tarefa.xp_reward; kc_ganho = tarefa.kc_reward
        aventureiro.xp += xp_ganho; aventureiro.kaicons += kc_ganho
        texto_tarefa = tarefa.texto
        db.session.delete(tarefa)
        
        adicionar_informe(f"{nome_aventureiro} completou: '{texto_tarefa}' (+{xp_ganho} XP, +{kc_ganho} KÇ).")
        verificar_level_up(aventureiro)
        
        db.session.commit()
        return jsonify({"message": f"Recompensa dada a {nome_aventureiro}."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

# --- GERENCIAMENTO DE ALERTAS ---
@app.route('/api/alertas', methods=['POST'])
def add_alerta():
    try:
        data = request.json
        if not data or 'texto' not in data: return jsonify({"erro": "Texto do alerta é obrigatório"}), 400
        adicionar_alerta_global(data['texto'])
        return jsonify({"message": "Alerta enviado"}), 201
    except Exception as e: return jsonify({"erro": str(e)}), 500
@app.route('/api/alertas', methods=['DELETE'])
def clear_alertas():
    global ALERTAS_DB
    ALERTAS_DB.clear()
    return jsonify({"message": "Alertas limpos"}), 200

# --- GERENCIAMENTO DE CRONOGRAMAS (Eventos) ---
@app.route('/api/cronogramas', methods=['POST'])
def add_cronograma():
    try:
        data = request.json
        texto = data.get('texto'); hora_str = data.get('hora')
        if not texto or not hora_str: return jsonify({"erro": "Hora e texto são obrigatórios"}), 400
        try:
            h, m = hora_str.split(':'); hora_int = int(h); minuto_int = int(m)
        except Exception: return jsonify({"erro": "Formato de hora inválido. Use HH:MM"}), 400
        novo_cronograma = Cronograma(hora=hora_int, minuto=minuto_int, texto=texto)
        db.session.add(novo_cronograma); db.session.commit()
        return jsonify(novo_cronograma.to_dict()), 201
    except Exception as e: return jsonify({"erro": str(e)}), 500
@app.route('/api/cronogramas/<int:id>', methods=['DELETE'])
def delete_cronograma(id):
    cronograma = Cronograma.query.get(id)
    if cronograma:
        db.session.delete(cronograma); db.session.commit()
        return jsonify({"message": "Cronograma removido"}), 200
    return jsonify({"erro": "Cronograma não encontrado"}), 404

# --- GERENCIAMENTO DE RODÍZIO (Tarefas Comunitárias) ---
@app.route('/api/rodizio', methods=['GET'])
def get_rodizio():
    hoje = datetime.now().date()
    jogadores = get_lista_nomes_jogadores()
    tarefas = Rodizio.query.order_by(Rodizio.id).all()
    atribuicoes_hoje = calcular_atribuicao(hoje, jogadores, tarefas)
    tarefas_lista = [t.to_dict() for t in tarefas]
    return jsonify({"atribuicoes_hoje": atribuicoes_hoje, "tipos_de_tarefa": tarefas_lista})
@app.route('/api/rodizio', methods=['POST'])
def add_rodizio():
    try:
        data = request.json
        nome = data.get('nome_tarefa'); desc = data.get('descricao')
        if not nome or not desc:
            return jsonify({"erro": "Nome da tarefa e descrição são obrigatórios"}), 400
        nova_tarefa_rodizio = Rodizio(nome_tarefa=nome, descricao=desc)
        db.session.add(nova_tarefa_rodizio); db.session.commit()
        adicionar_informe(f"Nova tarefa comunitária criada: {nome}")
        return jsonify(nova_tarefa_rodizio.to_dict()), 201
    except Exception as e: return jsonify({"erro": str(e)}), 500
@app.route('/api/rodizio/<int:id>', methods=['DELETE'])
def delete_rodizio_tarefa(id):
    tarefa_rodizio = Rodizio.query.get(id)
    if tarefa_rodizio:
        nome_tarefa = tarefa_rodizio.nome_tarefa
        db.session.delete(tarefa_rodizio); db.session.commit()
        adicionar_informe(f"Tarefa comunitária removida: {nome_tarefa}")
        return jsonify({"message": "Tipo de tarefa de rodízio removida"}), 200
    return jsonify({"erro": "Tipo de tarefa de rodízio não encontrada"}), 404

# (POST /api/informes)
@app.route('/api/informes', methods=['POST'])
def add_informe_manual():
    data = request.json
    texto = data.get('texto')
    if not texto: return jsonify({"erro": "Texto do informe é obrigatório"}), 400
    adicionar_informe(f"[INFORME MANUAL] {texto}")
    return jsonify({"message": "Informe adicionado ao registro."}), 201

# (POST /api/aventureiro/ajustar-stats)
@app.route('/api/aventureiro/ajustar-stats', methods=['POST'])
def adjust_stats():
    data = request.json
    nome_aventureiro = data.get('nome_aventureiro')
    aventureiro = Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first()
    if not aventureiro: return jsonify({"erro": "Aventureiro não encontrado."}), 404
    try:
        log_msgs = []; xp_adicionado = False
        if data.get('kaicons') is not None:
            quantia = int(data.get('kaicons'))
            if (aventureiro.kaicons + quantia) < 0: return jsonify({"erro": "Ajuste de KÇ deixaria o saldo negativo."}), 400
            aventureiro.kaicons += quantia
            log_msgs.append(f"{quantia} KÇ")
        if data.get('xp') is not None:
            quantia = int(data.get('xp'))
            if (aventureiro.xp + quantia) < 0: aventureiro.xp = 0
            else: aventureiro.xp += quantia
            log_msgs.append(f"{quantia} XP")
            xp_adicionado = True
        if data.get('nivel') is not None:
            aventureiro.nivel = int(data.get('nivel'))
            log_msgs.append(f"Nível para {data.get('nivel')}")
        if data.get('habilidades') is not None:
            aventureiro.habilidades = data.get('habilidades')
            log_msgs.append(f"Habilidades atualizadas")
        if not log_msgs: return jsonify({"erro": "Nenhum dado válido enviado para ajuste."}), 400
        if xp_adicionado:
            verificar_level_up(aventureiro)
        log_final = f"[GM] ajustou {nome_aventureiro}: " + ", ".join(log_msgs)
        adicionar_informe(log_final)
        db.session.commit()
        return jsonify(aventureiro.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

# (POST /api/aventureiro/ajustar-inventario)
@app.route('/api/aventureiro/ajustar-inventario', methods=['POST'])
def adjust_inventario():
    data = request.json
    nome_aventureiro = data.get('nome_aventureiro')
    item_nome = data.get('item_nome')
    try: quantia = int(data.get('quantia'))
    except (ValueError, TypeError): return jsonify({"erro": "Quantia inválida."}), 400
    if not nome_aventureiro or not item_nome or quantia == 0:
        return jsonify({"erro": "Nome, item e quantia (não-zero) são obrigatórios."}), 400
    aventureiro = Aventureiro.query.filter_by(nome_aventureiro=nome_aventureiro).first()
    if not aventureiro: return jsonify({"erro": "Aventureiro não encontrado."}), 404
    try:
        inventario = json.loads(aventureiro.inventario)
    except json.JSONDecodeError: inventario = {}
    nome_item_normalizado = item_nome.strip().lower()
    quantia_atual = inventario.get(nome_item_normalizado, 0)
    nova_quantia = quantia_atual + quantia
    if nova_quantia < 0:
        return jsonify({"erro": f"Não é possível remover {abs(quantia)}. O jogador só tem {quantia_atual}."}), 400
    elif nova_quantia == 0:
        if nome_item_normalizado in inventario:
            del inventario[nome_item_normalizado]
    else:
        inventario[nome_item_normalizado] = nova_quantia
    aventureiro.inventario = json.dumps(inventario)
    acao = "adicionado(s)" if quantia > 0 else "removido(s)"
    adicionar_informe(f"[GM] {abs(quantia)}x '{nome_item_normalizado}' {acao} do inventário de {nome_aventureiro}.")
    db.session.commit()
    return jsonify(aventureiro.to_dict()), 200

# --- GERENCIAMENTO DA LOJA (GM) ---
@app.route('/api/loja-item', methods=['POST'])
def add_loja_item():
    try:
        data = request.json
        nome = data.get('nome'); desc = data.get('descricao')
        preco = int(data.get('preco')); estoque = int(data.get('estoque_inicial', 0))
        if not nome or not desc or preco < 0:
            return jsonify({"erro": "Nome, descrição e preço (positivo) são obrigatórios."}), 400
        if LojaItem.query.filter_by(nome=nome).first():
            return jsonify({"erro": "Um item com este nome já existe na loja."}), 400
        novo_item = LojaItem(nome=nome, descricao=desc, preco=preco, estoque=estoque)
        db.session.add(novo_item); db.session.commit()
        adicionar_informe(f"[LOJA] Novo item à venda: {nome} por {preco} KÇ (Estoque: {estoque}).")
        return jsonify(novo_item.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/loja-item/<int:id>', methods=['DELETE'])
def delete_loja_item(id):
    item = LojaItem.query.get(id)
    if item:
        nome_item = item.nome
        db.session.delete(item); db.session.commit()
        adicionar_informe(f"[LOJA] Item removido da loja: {nome_item}.")
        return jsonify({"message": "Item removido da loja"}), 200
    return jsonify({"erro": "Item não encontrado"}), 404
@app.route('/api/loja/ajustar', methods=['POST'])
def adjust_loja_item():
    data = request.json
    item_id = data.get('item_id')
    item = LojaItem.query.get(item_id)
    if not item:
        return jsonify({"erro": "Item da loja não encontrado."}), 404
    try:
        log_msgs = []
        if data.get('novo_preco') is not None:
            item.preco = int(data.get('novo_preco'))
            log_msgs.append(f"preço ajustado para {item.preco} KÇ")
        if data.get('adicionar_estoque') is not None:
            quantia = int(data.get('adicionar_estoque'))
            if (item.estoque + quantia) < 0:
                item.estoque = 0
            else:
                item.estoque += quantia
            log_msgs.append(f"estoque ajustado em {quantia} (Total: {item.estoque})")
        if not log_msgs:
            return jsonify({"erro": "Nenhum dado válido enviado."}), 400
        adicionar_informe(f"[LOJA] Item '{item.nome}' atualizado: " + ", ".join(log_msgs))
        db.session.commit()
        return jsonify(item.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/informes/loja', methods=['GET'])
def get_informes_loja():
    informes_db = RegistroInformes.query.filter(RegistroInformes.texto.like('%[LOJA]%')).order_by(RegistroInformes.timestamp.desc()).limit(50).all()
    return jsonify([informe.to_dict() for informe in informes_db])

# --- MÓDULO DE CONTROLE DO HABITAT ---
@app.route('/api/habitat/sistemas', methods=['GET'])
def get_habitat_sistemas():
    sistemas = HabitatSistema.query.order_by(HabitatSistema.id).all()
    return jsonify([s.to_dict() for s in sistemas])
@app.route('/api/habitat/sistemas/<int:id>/status', methods=['PUT'])
def set_habitat_sistema_status(id):
    sistema = HabitatSistema.query.get(id)
    if not sistema:
        return jsonify({"erro": "Sistema do Habitat não encontrado."}), 404
    try:
        if sistema.status == 'FUNCIONAL':
            sistema.status = 'DANIFICADO'
            alerta_texto = f"ALERTA: Falha crítica detectada no {sistema.nome} ({sistema.setor})!"
            adicionar_alerta_global(alerta_texto)
            tarefa_texto = f"Reparar o {sistema.nome} ({sistema.setor})"
            tarefa_existente = Tarefa.query.filter_by(texto=tarefa_texto).first()
            if not tarefa_existente:
                nova_tarefa = Tarefa(texto=tarefa_texto, xp_reward=100, kc_reward=50)
                db.session.add(nova_tarefa)
                adicionar_informe(f"Nova Tarefa (Quest) gerada por falha no sistema: {tarefa_texto}")
        else:
            sistema.status = 'FUNCIONAL'
            adicionar_informe(f"[SISTEMA] O {sistema.nome} ({sistema.setor}) foi reparado e está FUNCIONAL.")
        db.session.commit()
        return jsonify(sistema.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
        
# --- ROTAS DE GERENCIAMENTO DE NPCs E MAPA DE RASTREAMENTO ---
@app.route('/api/npcs', methods=['GET'])
def get_npcs():
    npcs = NPC.query.order_by(NPC.nome).all()
    return jsonify([npc.to_dict() for npc in npcs])
@app.route('/api/npcs', methods=['POST'])
def add_npc():
    try:
        data = request.json
        nome = data.get('nome'); desc = data.get('descricao'); local = data.get('localizacao', 'Germinal')
        if not nome:
            return jsonify({"erro": "Nome do NPC é obrigatório."}), 400
        if NPC.query.filter_by(nome=nome).first():
            return jsonify({"erro": "Um NPC com este nome já existe."}), 400
        novo_npc = NPC(nome=nome, descricao=desc, localizacao_atual=local)
        db.session.add(novo_npc); db.session.commit()
        adicionar_informe(f"[SISTEMA] NPC '{nome}' foi adicionado ao Habitat.")
        return jsonify(novo_npc.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/npcs/<int:id>', methods=['DELETE'])
def delete_npc(id):
    npc = NPC.query.get(id)
    if npc:
        nome_npc = npc.nome
        db.session.delete(npc); db.session.commit()
        adicionar_informe(f"[SISTEMA] NPC '{nome_npc}' foi removido do Habitat.")
        return jsonify({"message": "NPC removido"}), 200
    return jsonify({"erro": "NPC não encontrado"}), 404
@app.route('/api/npcs/<int:id>/localizacao', methods=['PUT'])
def move_npc(id):
    npc = NPC.query.get(id)
    if not npc:
        return jsonify({"erro": "NPC não encontrado."}), 404
    local = request.json.get('localizacao')
    if not local:
        return jsonify({"erro": "Localização não fornecida."}), 400
    try:
        npc.localizacao_atual = local
        db.session.commit()
        return jsonify(npc.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500
@app.route('/api/mapa/localizacoes', methods=['GET'])
def get_mapa_localizacoes():
    try:
        aventureiros = Aventureiro.query.all()
        loc_jogadores = [{"nome": a.nome_aventureiro, "local": a.localizacao_atual, "tipo": "jogador"} for a in aventureiros]
        npcs = NPC.query.all()
        loc_npcs = [{"nome": n.nome, "local": n.localizacao_atual, "tipo": "npc"} for n in npcs]
        return jsonify(loc_jogadores + loc_npcs)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# --- NOVAS ROTAS: GERENCIAMENTO DE PRODUÇÃO (GM) ---
@app.route('/api/receitas', methods=['GET'])
@jwt_required() # Protegido para GM e Jogador
def get_receitas():
    receitas = Receita.query.order_by(Receita.nome_item_final).all()
    return jsonify([r.to_dict() for r in receitas])

@app.route('/api/receitas', methods=['POST'])
def add_receita():
    try:
        data = request.json
        nome_item_final = data.get('nome_item_final')
        quantia_produzida = int(data.get('quantia_produzida', 1))
        ingredientes_json = data.get('ingredientes_json') 
        
        if not nome_item_final or not ingredientes_json:
            return jsonify({"erro": "Nome do item e ingredientes (JSON) são obrigatórios."}), 400
        try:
            json.loads(ingredientes_json)
        except json.JSONDecodeError:
            return jsonify({"erro": "Formato de Ingredientes JSON inválido."}), 400
            
        nova_receita = Receita(
            nome_item_final=nome_item_final.strip().lower(),
            quantia_produzida=quantia_produzida,
            ingredientes_json=ingredientes_json
        )
        db.session.add(nova_receita)
        db.session.commit()
        
        adicionar_informe(f"[OFICINA] Nova receita criada: {nova_receita.nome_item_final}")
        return jsonify(nova_receita.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

@app.route('/api/receitas/<int:id>', methods=['DELETE'])
def delete_receita(id):
    receita = Receita.query.get(id)
    if receita:
        nome_receita = receita.nome_item_final
        db.session.delete(receita)
        db.session.commit()
        adicionar_informe(f"[OFICINA] Receita removida: {nome_receita}.")
        return jsonify({"message": "Receita removida"}), 200
    return jsonify({"erro": "Receita não encontrada"}), 404

# --- FUNÇÃO DE INICIALIZAÇÃO DO BANCO DE DADOS ---
def create_initial_data():
    if Tarefa.query.first() is None:
        print("Criando tarefas iniciais...")
        db.session.add_all([
            Tarefa(texto="Sincronização de Rede (Setor 2)", xp_reward=50, kc_reward=10),
            Tarefa(texto="Coletar 'Manuscrito' (Setor 4)", xp_reward=100, kc_reward=25)
        ])
    if Cronograma.query.first() is None:
        print("Criando cronogramas iniciais...")
        db.session.add_all([
            Cronograma(hora=7, minuto=0, texto="Café da Manhã (Início)"),
            Cronograma(hora=7, minuto=45, texto="Café da Manhã (Finalizando)")
        ])
    if Rodizio.query.first() is None:
        print("Criando tarefas de rodízio iniciais...")
        db.session.add_all([
            Rodizio(nome_tarefa="Café da Manhã", descricao="servir, limpar e lavar louça"),
            Rodizio(nome_tarefa="Louça do Almoço", descricao="servir, limpar, lavar as panelas e o chão"),
            Rodizio(nome_tarefa="Louça da Janta", descricao="servir, limpar, lavar as panelas"),
            Rodizio(nome_tarefa="Banheiros", descricao="lavar, recolher o lixo e repor os produtos")
        ])
    if RegistroInformes.query.first() is None:
        print("Criando informe inicial...")
        adicionar_informe("Sistema Kaibora [v1.3] iniciado. Banco de dados online.")
    if ChatMensagem.query.first() is None:
        print("Criando mensagem de boas-vindas do chat...")
        db.session.add(
            ChatMensagem(nome_autor="Aropiak (Sistema)", texto="Bem-vindos ao Canal da Guilda. Este é o chat interno para todos os aventureiros registrados.")
        )
    if LojaItem.query.first() is None:
        print("Abastecendo a loja da Guilda...")
        db.session.add_all([
            LojaItem(nome="Ração de Viagem", descricao="Uma barra de nutrientes compactada.", preco=10, estoque=100),
            LojaItem(nome="Kit Médico Básico", descricao="Contém ataduras e antisséptico.", preco=50, estoque=20),
            LojaItem(nome="tecido", descricao="Retalho de tecido limpo.", preco=5, estoque=100),
            LojaItem(nome="antisseptico", descricao="Frasco de líquido esterilizante.", preco=30, estoque=100)
        ])
    if HabitatSistema.query.first() is None:
        print("Registrando sistemas do Habitat...")
        db.session.add_all([
            HabitatSistema(nome="Sistema Elétrico", setor="Setor 2"),
            HabitatSistema(nome="Sistema Hidráulico", setor="Setor 4"),
            HabitatSistema(nome="Rede de Comunicação", setor="Setor 1 (Central)"),
            HabitatSistema(nome="Rotas de Autônomos", setor="Setores 3 e 4")
        ])
    if EsbocoMapa.query.first() is None:
        print("Criando entrada de esboço de mapa inicial...")
        db.session.add(
            EsbocoMapa(nome_autor="Operador Antigo", nome_setor="Refeitório", notas="Layout original, antes do colapso do teto.")
        )
    if NPC.query.first() is None:
        print("Adicionando NPCs iniciais...")
        db.session.add_all([
            NPC(nome="Engenheiro Chefe (NPC)", descricao="Obsessivo com a manutenção.", localizacao_atual="Setor 6 (Oficinas)"),
            NPC(nome="Cozinheira (NPC)", descricao="Controla o estoque de alimentos.", localizacao_atual="Setor 4 (Refeitório)")
        ])
    
    # --- NOVO: Popula as Receitas Iniciais ---
    if Receita.query.first() is None:
        print("Adicionando receitas de produção iniciais...")
        r1 = Receita(
            nome_item_final="kit medico basico", 
            quantia_produzida=1,
            ingredientes_json='{"tecido": 2, "antisseptico": 1}'
        )
        db.session.add(r1)
        
    db.session.commit()

# --- Executa o Servidor ---
if __name__ == '__main__':
    if not os.path.exists('templates'): os.makedirs('templates')
    if not os.path.exists('static'): os.makedirs('static')
    with app.app_context():
        # db.drop_all() # CUIDADO: Descomente para resetar o DB (necessário desta vez)
        db.create_all()
        create_initial_data()
    print("Servidor do Mestre Kaibora iniciado.")
    print(f"Banco de dados está em: {os.path.join(base_dir, 'kaibora.db')}")
    print("Acesse o painel do GM em: http://127.0.0.1:5000/gm")
    app.run(debug=True, port=5000)