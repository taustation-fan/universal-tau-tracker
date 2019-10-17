import os
from utt.model import db
from flask_cors import CORS
from flask import Flask, render_template, send_from_directory

static_file_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static')

def make_app():
    app = Flask(__name__)
    #app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.environ.get('CTT_DB', '/tmp/utt.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql:///utt'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    CORS(app)
    return app

app = make_app()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory('static', path)
