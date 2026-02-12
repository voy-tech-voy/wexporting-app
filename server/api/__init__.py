from flask import Blueprint

api_bp = Blueprint('api', __name__)
webhook_bp = Blueprint('webhook', __name__)

from . import routes, webhooks, updates, app_config
