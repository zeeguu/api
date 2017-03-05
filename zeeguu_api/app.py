# -*- coding: utf8 -*-
import os
import os.path

import flask
import flask_assets
import flask_sqlalchemy


class CrossDomainApp(flask.Flask):
    """Allows cross-domain requests for all error pages"""
    def handle_user_exception(self, e):
        rv = super(CrossDomainApp, self).handle_user_exception(e)
        rv = self.make_response(rv)
        rv.headers['Access-Control-Allow-Origin'] = "*"
        return rv


# create the instance folder and return the path
def instance_path(app):
    path = os.path.join(app.instance_path, "gen")
    try:
        os.makedirs(path)
    except:
        if not os.path.isdir(path):
            raise
    return path

# *** Starting the App *** #
app = CrossDomainApp(__name__, instance_relative_config=True)

# Loading the configuration
app.config.from_object("zeeguu_api.default_config")
config_file = os.path.expanduser('~/.zeeguu/zeeguu_api.cfg')
if os.environ.has_key("CONFIG_FILE"):
    config_file = os.environ["CONFIG_FILE"]
print ('running with config file: ' + config_file)
app.config.from_pyfile(config_file, silent=False) #config.cfg is in the instance folder
instance = flask.Blueprint("instance", __name__, static_folder=instance_path(app))
print ('DB is: ' + app.config["SQLALCHEMY_DATABASE_URI"])

# the zeeguu core model expects a bunch of configuration stuff to be available in the zeeguu.app.config
# we bind our current app.config to the zeeguu.app.config so that code does not break.
import zeeguu
zeeguu.app = app
zeeguu.app.config = app.config

# Important... let's initialize the models with a db object
db = flask_sqlalchemy.SQLAlchemy()
zeeguu.db = db
import zeeguu.model
# -------------------------------

env = flask_assets.Environment(app)
env.cache = app.instance_path
env.directory = os.path.join(app.instance_path, "gen")
env.url = "/gen"
env.append_path(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static"
), "/static")

db.init_app(app)
db.create_all(app=app)


from api import api
app.register_blueprint(instance)
app.register_blueprint(api)

# TODO: Look at this, but this should not be needed!
from zeeguu.model import RankedWord
with zeeguu.app.app_context():
    RankedWord.cache_ranked_words()


