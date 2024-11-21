#not sure yet what all this is. Have a look at it.
#To do: Import the file where the activity_and_commitment_by_user is located

import flask

from zeeguu.api.utils import json_result
from zeeguu.core.user_statistics.activity import activity_duration_by_day
from . import api
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from user_commitment import activity_and_commitment_by_user

@api.route("/user_activity_and_commitment", method=("GET",))
@cross_domain
@requires_session

def user_activity_and_commitment():
	"""
	User commitment info 
	"""
	user= User.find_by_id(flask.g.user_id)
	return json_result(activity_and_commitment_by_user(user))
	
	

