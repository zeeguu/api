import zeeguu_core
db = zeeguu_core.db


class WatchEventType(db.Model):
    __table_args__ = dict(mysql_collate='utf8_bin')
    __tablename__ = 'watch_event_type'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    def __init__(self, name):
        self.name = name

    @classmethod
    def find_by_name(cls, name):
        """
        :param name:
        :return: the desired object, or None if it does not exist
        """
        try:
            return WatchEventType.query.filter_by(name=name).first()
        except:
            return None


