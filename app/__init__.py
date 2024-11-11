from flask import Flask
from rpy2.robjects.conversion import converter
import threading

def create_app():
    app = Flask(__name__)
    
    # Each thread will have its own R environment
    def init_r():
        if not hasattr(threading.current_thread(), "_r_initialized"):
            threading.current_thread()._r_initialized = True
    
    # Configure the R initializer before each request
    @app.before_request
    def before_request():
        init_r()
    
    # Register the blueprint
    from .routes import main
    app.register_blueprint(main)
    
    return app