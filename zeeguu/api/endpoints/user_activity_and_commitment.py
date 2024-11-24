#not sure yet what all this is. Have a look at it.
#To do: Import the file where the activity_and_commitment_by_user is located


from zeeguu.core.user_statistics.activity import activity_duration_by_day
from . import api

import flask
from flask import request
from datetime import datetime

from . import api, db_session
from ...core.model.user_commitment import UserCommitment
from zeeguu.api.utils import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from user_commitment_and_activity import activity_and_commitment_by_user
from user_commitment_and_activity import commitment_by_user, activity_and_commitment_by_user
from zeeguu.core.user_statistics.user_commitment_and_activity import activity_and_commitment_by_user
from zeeguu.core.user_statistics.user_commitment_and_activity import commitment_by_user

@api.route("/user_activity_and_commitment", methods=("GET",))
@cross_domain
@requires_session
def user_activity_and_commitment():
    """
    User activity and commitment info 
    """
    user= User.find_by_id(flask.g.user_id)
    commitment_info = activity_and_commitment_by_user(user)
    return json_result(commitment_info)


@api.route("/user_commitment", methods=("GET",))
@cross_domain
@requires_session

def user_commitment():	
  
    """
    User commitment info
    """
    user = User.find_by_id(flask.g.user_id)
    return json_result(commitment_by_user(user))
    
 


## Sends the minutes and days that the user chooses to the database 
@api.route(
    "/user_commitment_create",
    methods=["POST"],
)
@requires_session
def create_user_commitment():
    user_minutes = int(request.form.get("user_minutes", ""))
    user_days = int(request.form.get("user_days",""))
    commitment = UserCommitment(flask.g.user_id, user_minutes, user_days, consecutive_weeks=0)
    db_session.add(commitment)
    db_session.commit()
    return json_result(dict(id=commitment.id))


# Sends the value for consecutive weeks to the database, this will be used on a weekly basis to update the value 
@api.route(
    "/user_commitment_update",
    methods=["PUT"],
)
@requires_session
def update_user_commitment():
    consecutive_weeks = int(request.json.get("consecutive_weeks", ""))
    commitment_last_updated = datetime(request.json.get("commitment_last_updated", ""))
    commitment = db_session.query(UserCommitment).filter_by(user_id=flask.g.user_id).first()
    commitment.consecutive_weeks = consecutive_weeks
    commitment.commitment_last_updated = commitment_last_updated
    db_session.commit()
    return json_result(dict(id=commitment.id))

       
   
