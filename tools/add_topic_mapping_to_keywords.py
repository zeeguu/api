import pandas as pd
from zeeguu.core.model.topic_keyword import TopicKeyword
from zeeguu.core.model.new_topic import NewTopic
import zeeguu.core
from tqdm import tqdm
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session


df = pd.read_csv("url_topics_count_with_pred_to_db.csv", index_col=0)

for row_i, row in tqdm(df.iterrows()):
    keyword = row["keyword"]
    try:
        topic_k_list = TopicKeyword.find_all_by_keyword(keyword)
        print(topic_k_list)
        for topic_k in topic_k_list:
            topic_to_assign = (
                NewTopic.find_by_id(row["val_pred"]) if row["val_pred"] != -1 else None
            )
            print(topic_to_assign)
            topic_k.new_topic = topic_to_assign
            db_session.add(topic_k)
    except Exception as e:
        print(f"Failed for '{keyword}', with: {e}")
db_session.commit()
