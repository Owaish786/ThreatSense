from flask import Flask, jsonify
from flask_cors import CORS

from app.api.routes.predict import predict_bp
from app.db.base import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    init_db()
    app.register_blueprint(predict_bp)

    @app.get('/api/health')
    def health() -> tuple:
        return jsonify({'status': 'ok', 'service': 'ThreatSense API'}), 200

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
