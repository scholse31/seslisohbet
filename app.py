from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
import random
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Basit route - template olmadan
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sohbet Uygulaması</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            button { background: #3498db; color: white; padding: 15px 30px; border: none; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>🚀 Sohbet Uygulaması Çalışıyor!</h1>
        <p>Backend başarıyla deploy edildi.</p>
        <button onclick="alert('Çalışıyor!')">Test Butonu</button>
    </body>
    </html>
    """

# Diğer API route'ları buraya aynen kopyala...
@app.route('/api/create_room', methods=['POST'])
def create_room():
    # Önceki kodun aynısı
    pass

# SocketIO event'leri buraya...

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
