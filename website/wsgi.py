from main import app
from waitress import serve

def create_app():
    return app