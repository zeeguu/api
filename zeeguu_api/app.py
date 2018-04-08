# -*- coding: utf8 -*-
from zeeguu.configuration.configuration import load_configuration_or_abort
from flask_cors import CORS
from flask import Flask
import flask
import flask_monitoringdashboard as dashboard

# *** Creating and starting the App *** #
app = Flask("Zeeguu-API")
CORS(app)

load_configuration_or_abort(app,
                            'ZEEGUU_API_CONFIG',
                            [  # first three are required by core
                                'MAX_SESSION',
                                'SQLALCHEMY_DATABASE_URI',
                                'SQLALCHEMY_TRACK_MODIFICATIONS',
                                # next three are required by API when
                                # run locally
                                'DEBUG',
                                'HOST',
                                'SECRET_KEY', ])

# The zeeguu.model  module relies on an app being injected from outside
# ----------------------------------------------------------------------
import zeeguu

zeeguu.app = app
import zeeguu.model

assert zeeguu.model
# -----------------

from .api import api

app.register_blueprint(api)

dashboard.config.init_from(envvar='DASHBOARD_CONFIG')

from zeeguu.model import Session

#dashboard.config.get_group_by = lambda: Session.find(request=flask.request).user_id
dashboard.bind(app=app, blue_print=api)
