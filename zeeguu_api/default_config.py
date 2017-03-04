# -*- coding: utf8 -*-

HOST = "127.0.0.1"
PORT = 9000
DEBUG = True
SECRET_KEY = 'debuggingkey'

SQLALCHEMY_DATABASE_URI = ("mysql://root:password@localhost/zeeguu_performance_test")
MAX_SESSION=99999999
SQLALCHEMY_TRACK_MODIFICATIONS=False