# script used to convert the old binary hashes
# to their hex counterparts. binary can not be
# insured UNIQUE by a mysql constraint
import zeeguu_core
from zeeguu_core import util
from zeeguu_core.model import Text

session = zeeguu_core.db.session

texts = session.query(Text).all()
for t in texts:
    t.content_hash = util.text_hash(t.content)
    session.add(t)
    session.commit()
# input ("next?/")
