#not sure yet what all this is. Have a look at it.

import flask

from zeeguu.api.utils import json_result
from zeeguu.core.user_statistics.activity import activity_duration_by_day
from . import api
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User

@api.route("/data_user_commitment", method=("GET",))
@cross_domain
@requires_session

def data_user_commitment():
	"""
	User commitment info 
	"""
	user= User.find_by_id(flask.g.user_id)
	return json_result(commitment_by_user(user))