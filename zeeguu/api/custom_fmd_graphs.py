def daily_visitors(dashboard):
    def active_users_today():
        from zeeguu.core.model import User

        return len(User.all_recent_user_ids(days=1))

    schedule = {
        "hours": 23,
        "minutes": 58,
        # 'seconds': 1
    }
    dashboard.add_graph("Daily Visitors", lambda: active_users_today(), **schedule)
