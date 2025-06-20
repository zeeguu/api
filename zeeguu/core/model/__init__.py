from .db import db

# Import registry to ensure all models are registered with SQLAlchemy
# This is necessary for db.create_all() to work properly
from . import registry