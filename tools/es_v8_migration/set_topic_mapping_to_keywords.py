import pandas as pd
from zeeguu.core.model.url_keyword import UrlKeyword
from zeeguu.core.model.new_topic import NewTopic
import zeeguu.core
from tqdm import tqdm
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session

"""
    Assigns the url_keywords a specific topic based on manual labeling.
    The file was generated before we seperated them based on different languages.
    This should be considered a starting point and should be monitored overtime to 
    identify possible errors in the labeling or new labels that become relevant.
"""
df = pd.read_csv("url_topics_count_with_pred_to_db.csv", index_col=0)

for row_i, row in tqdm(df.iterrows()):
    keyword = row["keyword"]
    try:
        url_k_list = UrlKeyword.find_all_by_keyword(keyword)
        for url_k in url_k_list:
            topic_to_assign = (
                NewTopic.find_by_id(row["val_pred"]) if row["val_pred"] != -1 else None
            )
            url_k.new_topic = topic_to_assign
            db_session.add(url_k)
    except Exception as e:
        print(f"Failed for '{keyword}', with: {e}")
db_session.commit()
