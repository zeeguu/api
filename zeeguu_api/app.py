# -*- coding: utf8 -*-
from cross_domain_app import CrossDomainApp
from zeeguu.util.configuration import load_configuration_or_abort
from flask_cors import CORS, cross_origin
from flask import Flask

# *** Creating and starting the App *** #
app = Flask("Zeeguu-API")
CORS(app)

load_configuration_or_abort(app, 'ZEEGUU_API_CONFIG',
                            ['SQLALCHEMY_DATABASE_URI', 'HOST', 'DEBUG', 'SECRET_KEY', 'MAX_SESSION'])


# The zeeguu.model  module relies on an app being injected from outside
# ----------------------------------------------------------------------
import zeeguu
zeeguu.app = app
import zeeguu.model
assert zeeguu.model
# -----------------

from api import api
app.register_blueprint(api)
