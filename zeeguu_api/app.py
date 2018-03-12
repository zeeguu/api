# -*- coding: utf8 -*-
from zeeguu.configuration.configuration import load_configuration_or_abort
from flask_cors import CORS
from flask import Flask

# *** Creating and starting the App *** #
app = Flask("Zeeguu-API")
CORS(app)

load_configuration_or_abort(app, 'ZEEGUU_API_CONFIG',
                            ['SQLALCHEMY_DATABASE_URI', 'HOST', 'DEBUG', 'SECRET_KEY', 'MAX_SESSION'])

dashboard_enabled = True

# The zeeguu.model  module relies on an app being injected from outside
# ----------------------------------------------------------------------
import zeeguu

zeeguu.app = app
import zeeguu.model

assert zeeguu.model
# -----------------

from .api import api

app.register_blueprint(api)

if dashboard_enabled:
    try:
        import flask_monitoringdashboard as dashboard

        dashboard.config.init_from(envvar='DASHBOARD_CONFIG')


        # dashboard can benefit from a way of associating a request with a user id
        def get_user_id():
            import flask
            try:
                session_id = int(flask.request.args['session'])
            except:
                print("cound not find the session in the request")
                return 1
            from zeeguu.model import Session
            session = Session.find_for_id(session_id)

            user_id = session.user.id
            return user_id


        dashboard.config.get_group_by = get_user_id
        dashboard.bind(app=app, blue_print=api)
    except ModuleNotFoundError as e:
        print("Running without dashboard (module not present)")
    except Exception as e:
        print(f"Running without dashboard ({e})")
