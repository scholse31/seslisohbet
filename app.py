from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import random
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Veritabanı yerine geçici depolama
active_connections = {}
active_users = {}
rooms = {}
MAX_USERS_PER_ROOM = 10

class Connection:
    def __init__(self, code, host):
        self.code = code
        self.host = host
        self.users = [host]
        self.messages = []
        self.created_at = datetime.now()
    
    def add_user(self, user):
        if len(self.users) >= MAX_USERS_PER_ROOM:
            return False, "Oda dolu (Maksimum 10 kişi)"
        
        if any(u['username'] == user['username'] for u in self.users):
            return False, "Bu kullanıcı adı zaten kullanılıyor"
        
        self.users.append(user)
        return True, "Kullanıcı eklendi"
    
    def remove_user(self, username):
        self.users = [user for user in self.users if user['username'] != username]
        return len(self.users) > 0  # Oda boşsa True döner
    
    def add_message(self, message):
        self.messages.append(message)
        if len(self.messages) > 100:  # Mesaj geçmişini sınırla
            self.messages = self.messages[-50:]

@app.route('/')
def home():
    return jsonify({"message": "Sohbet Backend API", "status": "running"})

@app.route('/api/create_room', methods=['POST'])
def create_room():
    data = request.get_json()
    username = data.get('username')
    
    if not username:
        return jsonify({"success": False, "message": "Kullanıcı adı gerekli"})
    
    # 4 haneli kod oluştur (1-6 arası rakamlar)
    code = ''.join(str(random.randint(1, 6)) for _ in range(4))
    
    # Benzersiz kod bul
    while code in active_connections:
        code = ''.join(str(random.randint(1, 6)) for _ in range(4))
    
    user_data = {
        'username': username,
        'avatar': username[0].upper(),
        'sid': None,
        'joined_at': datetime.now()
    }
    
    connection = Connection(code, user_data)
    active_connections[code] = connection
    active_users[username] = code
    
    return jsonify({
        "success": True,
        "code": code,
        "message": "Oda oluşturuldu"
    })

@app.route('/api/join_room', methods=['POST'])
def join_room_api():
    data = request.get_json()
    code = data.get('code')
    username = data.get('username')
    
    if not code or not username:
        return jsonify({"success": False, "message": "Kod ve kullanıcı adı gerekli"})
    
    if code not in active_connections:
        return jsonify({"success": False, "message": "Geçersiz oda kodu"})
    
    if username in active_users:
        return jsonify({"success": False, "message": "Bu kullanıcı adı zaten kullanılıyor"})
    
    user_data = {
        'username': username,
        'avatar': username[0].upper(),
        'sid': None,
        'joined_at': datetime.now()
    }
    
    connection = active_connections[code]
    success, message = connection.add_user(user_data)
    
    if success:
        active_users[username] = code
        return jsonify({
            "success": True,
            "message": "Odaya katıldınız",
            "users": [user['username'] for user in connection.users]
        })
    else:
        return jsonify({"success": False, "message": message})

@app.route('/api/room_info/<code>')
def room_info(code):
    if code not in active_connections:
        return jsonify({"success": False, "message": "Oda bulunamadı"})
    
    connection = active_connections[code]
    return jsonify({
        "success": True,
        "code": code,
        "users": [{"username": user['username'], "avatar": user['avatar']} for user in connection.users],
        "user_count": len(connection.users),
        "host": connection.host['username']
    })

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    
    # Kullanıcıyı aktif kullanıcılardan ve odalardan kaldır
    username_to_remove = None
    room_code = None
    
    for username, code in active_users.items():
        for user in active_connections.get(code, {}).get('users', []):
            if user.get('sid') == request.sid:
                username_to_remove = username
                room_code = code
                break
    
    if username_to_remove and room_code:
        handle_leave_room({'username': username_to_remove, 'code': room_code})

@socketio.on('join_room')
def handle_join_room(data):
    code = data.get('code')
    username = data.get('username')
    
    if not code or not username:
        return
    
    if code in active_connections:
        join_room(code)
        
        # Kullanıcının socket ID'sini kaydet
        connection = active_connections[code]
        for user in connection.users:
            if user['username'] == username:
                user['sid'] = request.sid
                break
        
        # Tüm kullanıcılara yeni kullanıcı listesini gönder
        emit('user_joined', {
            'username': username,
            'users': [{"username": user['username'], "avatar": user['avatar']} for user in connection.users],
            'user_count': len(connection.users),
            'timestamp': datetime.now().isoformat()
        }, room=code)
        
        # Mesaj geçmişini gönder
        emit('message_history', {
            'messages': connection.messages[-50:]  # Son 50 mesaj
        }, room=request.sid)

@socketio.on('leave_room')
def handle_leave_room(data):
    code = data.get('code')
    username = data.get('username')
    
    if code in active_connections and username:
        connection = active_connections[code]
        
        # Kullanıcıyı odadan kaldır
        room_empty = connection.remove_user(username)
        
        # Aktif kullanıcılardan kaldır
        if username in active_users:
            del active_users[username]
        
        leave_room(code)
        
        # Diğer kullanıcılara bildir
        emit('user_left', {
            'username': username,
            'users': [{"username": user['username'], "avatar": user['avatar']} for user in connection.users],
            'user_count': len(connection.users),
            'timestamp': datetime.now().isoformat()
        }, room=code)
        
        # Oda boşsa temizle
        if room_empty:
            del active_connections[code]

@socketio.on('send_message')
def handle_send_message(data):
    code = data.get('code')
    username = data.get('username')
    message = data.get('message')
    
    if not all([code, username, message]):
        return
    
    if code in active_connections:
        connection = active_connections[code]
        
        message_data = {
            'id': str(int(time.time() * 1000)),
            'username': username,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'type': 'text'
        }
        
        connection.add_message(message_data)
        
        # Tüm odadaki kullanıcılara mesajı gönder
        emit('new_message', message_data, room=code)

@socketio.on('start_voice_call')
def handle_start_voice_call(data):
    code = data.get('code')
    username = data.get('username')
    
    if code in active_connections:
        emit('voice_call_started', {
            'started_by': username,
            'timestamp': datetime.now().isoformat()
        }, room=code)

@socketio.on('end_voice_call')
def handle_end_voice_call(data):
    code = data.get('code')
    username = data.get('username')
    
    if code in active_connections:
        emit('voice_call_ended', {
            'ended_by': username,
            'timestamp': datetime.now().isoformat()
        }, room=code)

@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    code = data.get('code')
    offer = data.get('offer')
    username = data.get('username')
    
    # Teklifi odadaki diğer kullanıcılara ilet (gönderen hariç)
    emit('webrtc_offer', {
        'offer': offer,
        'from': username
    }, room=code, include_self=False)

@socketio.on('webrtc_answer')
def handle_webrtc_answer(data):
    code = data.get('code')
    answer = data.get('answer')
    username = data.get('username')
    
    # Cevabı odadaki diğer kullanıcılara ilet (gönderen hariç)
    emit('webrtc_answer', {
        'answer': answer,
        'from': username
    }, room=code, include_self=False)

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    code = data.get('code')
    candidate = data.get('candidate')
    username = data.get('username')
    
    # ICE candidate'ı odadaki diğer kullanıcılara ilet (gönderen hariç)
    emit('ice_candidate', {
        'candidate': candidate,
        'from': username
    }, room=code, include_self=False)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)