#not sure yet what all this is. Have a look at it.
#To do: Import the file where the activity_and_commitment_by_user is located

import flask
from flask import request


from . import api, db_session
from ...core.model import UserCommitment
from zeeguu.api.utils import json_result
from . import api
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from user_commitment_and_activity import activity_and_commitment_by_user

@api.route("/user_activity_and_commitment", method=("GET",))
@cross_domain
@requires_session

def user_activity_and_commitment():
	"""
	User commitment info 
	"""
	user= User.find_by_id(flask.g.user_id)
	return json_result(activity_and_commitment_by_user(user))
	


## Sends the minutes and days that the user chooses to the database 
@api.route(
    "/user_commitment",
    methods=["POST"],
)
@requires_session
def user_commitment():
    user_minutes = int(request.form.get("user_minutes", ""))
    user_days = int(request.form.get("user_days",""))
    consecutive_weeks = int(request.form.get("consecutive_weeks",""))
    commitment = UserCommitment(flask.g.user_id, user_minutes, user_days)
    db_session.add(commitment)
    db_session.commit()
    return json_result(dict(id=commitment.id))

