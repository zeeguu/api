from activity import activity_duration_by_day
from sqlalchemy import text
import zeeguu.core.model
from datetime import datetime
	
def activity_and_commitment_by_user(user):
	return{ "user_minutes": commitment_mins(user) or 0,
					"user_days": commitment_days(user) or 0 ,
					"consecutive_weeks": commitment_consecutive_weeks(user) or 0,
					"commitment_last_updated": (
            			commitment_commitment_last_updated(user).strftime("%Y-%m-%d %H:%M:%S")
            			if commitment_commitment_last_updated(user)
            			else None
        			),
					"activity_time_by_day": activity_duration_by_day(user),
	}

def commitment_by_user(user):
	return { 
		"user_minutes": commitment_mins(user),
		"user_days": commitment_days(user),
	}

def commitment_mins(user):
	return _commitment_data_by_user(user, "user_commitment", "user_minutes")
def commitment_days(user):
	return _commitment_data_by_user(user, "user_commitment", "user_days")
def commitment_consecutive_weeks(user):
	return _commitment_data_by_user(user, "user_commitment", "consecutive_weeks")
def commitment_commitment_last_updated(user):
	return _commitment_data_by_user(user, "user_commitment", "commitment_last_updated")



def _commitment_data_by_user(user, table_name, user_commitment_data):
    query = (
            f" SELECT {user_commitment_data} "
            + f" FROM {table_name} "
			+ " WHERE user_id = :uid;"
    )
    result_raw = zeeguu.core.model.db.session.execute(
        text(query),
        {"uid": user.id, "table_name": table_name},
    )

    return result_raw
