# -*- coding: utf8 -*-
import os
import os.path

import flask
import flask_assets
import flask_sqlalchemy
from configuration import select_config_file
from cross_domain_app import CrossDomainApp
import zeeguu

# *** Creating and starting the App *** #
app = CrossDomainApp(__name__, instance_relative_config=True)


# Loading the external configuration
app.config.from_object("zeeguu_api.default_config")
app.config.from_pyfile(select_config_file(), silent=False)
print ('Running with DB : ' + app.config["SQLALCHEMY_DATABASE_URI"])

# The zeeguu core model expects a bunch of configuration stuff
# to be available in the zeeguu.app.config
# we bind our current app.config to the zeeguu.app.config
zeeguu.app = app
zeeguu.app.config = app.config

# Important... We must initialize the models with a db object!!
# BEGIN MODEL INITIALIZATION
db = flask_sqlalchemy.SQLAlchemy()
zeeguu.db = db
import zeeguu.model
db.init_app(app)
db.create_all(app=app)
# END MODEL INITIALIZATION
# -------------------------------

from api import api
app.register_blueprint(api)
