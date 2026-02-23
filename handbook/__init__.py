from flask import Blueprint

handbook_bp = Blueprint('handbook', __name__,
                        template_folder='../templates/handbook',
                        url_prefix='/handbook')

from handbook import routes  # noqa: E402, F401
