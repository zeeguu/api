#not sure yet what all this is. Have a look at it.
#To do: Import the file where the activity_and_commitment_by_user is located
import flask
from flask import request


from zeeguu.api.utils import json_result
from . import api, db_session
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from datetime import datetime


from zeeguu.core.model import User
from zeeguu.core.model import UserCommitment
import zeeguu.core.model


from zeeguu.core.user_statistics.activity import activity_duration_by_day



@api.route("/user_activity_and_commitment", methods=("GET",))
@cross_domain
@requires_session
def user_activity_and_commitment():
    """
    User activity and commitment info 
    """
    user = User.find_by_id(flask.g.user_id)
    user_commitment = UserCommitment.query.filter_by(user_id=user.id).first()
    user_activities = activity_duration_by_day(user)
    #commitment_info = activity_and_commitment_by_user(user)
    #return json_result(commitment_info)
    return json_result({
        "user_minutes": user_commitment.user_minutes,
        "user_days": user_commitment.user_days,
        "consecutive_weeks": user_commitment.consecutive_weeks,
        "commitment_last_updated": user_commitment.commitment_last_updated,
        "user_activities": user_activities,
    })


@api.route("/user_commitment", methods=("GET",))
@cross_domain
@requires_session
def user_commitment():
    """
    User commitment info
    """
    user = User.find_by_id(flask.g.user_id)
    user_commitment = UserCommitment.query.filter_by(user_id=user.id).first()
    print(user_commitment.user_minutes)
    return json_result({
        "user_minutes": user_commitment.user_minutes,
        "user_days": user_commitment.user_days,
    })
    
 


## Sends the minutes and days that the user chooses to the database 
@api.route(
    "/user_commitment_create",
    methods=["POST"]
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
    methods=["PUT"]
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

#sends the new values of user_minutes and user_days when the user updates it under settings. 
@api.route("/user_commitment_info", methods=["POST"])
@cross_domain
@requires_session
def user_commitment_info():
    """
    updates the number of days and minutes the user wants to practice
    under settings
    """
    user = User.find_by_id(flask.g.user_id)
    data = flask.request.form
    user_minutes = data.get("user_minutes")
    user_days = data.get("user_days")
    commitment = UserCommitment.query.filter_by(user_id=user.id).first()
    commitment.user_minutes = int(user_minutes)
    commitment.user_days = int(user_days)
    zeeguu.core.model.db.session.commit()
    print("I got here :)")
    return "OK"

       
   
