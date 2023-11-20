# script used to convert the old binary hashes
# to their hex counterparts. binary can not be
# insured UNIQUE by a mysql constraint
import zeeguu.core
from zeeguu.core import util
from zeeguu.core.model import Text

db_session = zeeguu.core.model.db.session

texts = db_session.query(Text).all()
for t in texts:
    t.content_hash = util.text_hash(t.content)
    db_session.add(t)
    db_session.commit()
# input ("next?/")
