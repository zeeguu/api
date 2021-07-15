#!/usr/bin/env python

"""

   Script that lists recent users

   To be called from a cron job.

"""

from zeeguu.core.model import User

for user_id in User.all_recent_user_ids():
    user = User.find_by_id(user_id)
    print (user.name)
    print (user.email)


            
