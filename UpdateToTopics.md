# Update to Topics

## 1. Update ElasticSearch to 8.\*

The first step is to update ES, as it supports KNN searches with dense vectors which will be used in the new way of classifying topics.

### 1.1. Update docker-compose with a new service that corresponds to the new version

I provided this under **elasticsearch_v8** in this codebase. We also need to set the `xpack.security.enabled=false` to allow us to connect via HTTP, otherwise we would need to set an SSL key. If, instead, we want to override the original **elasticsearch**, we need to first delete the index otherwise it will cause errors when trying to start up the ES server.

Personally, I recommend using the **\_v8** image, and once we are ready we can remove the old version and rename this to be the new **elasticsearch** image.

## 2. Create the API to provide the article embedding service.

I have created a folder for a small flask API application which will be in charge of embedding documents into dense vectors.
In the semanticEmbApi, it's include a dockerfile to create the image for this flask application, as well as the basic interface for a **semantic_vector** generator. In this case, we are using https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2 which can be downloaded from https://github.com/zeeguu/semantic-emb-api. The instructions are included and it will create a container which will be required by the new API to generate the sematnic vectors.

### 2.1. Include this image as a service in the docker-compose-v8.yml file

Within the `zeeguu.core` folder, we can find a new folder `semantic_vector_api`, which will include the logic to retrieve the dense vector given a document's content.

Currently, the connection is made at `ZEEGUU_EMB_API_CONN_STRING: "http://embedding_api:3654"` and the service is called `embedding_api`.

# Starting the deployment

For the deployment, and transition period we will use the containers named `dev_server_pre` and `elasticsearch_v8_pre` which runs on a different port and can index the documents in the background without interfering with the dev_server running the production server.

At the end of the process, we can run the default `dev_server` and `elasticsearch_v8` which run on the default ports and replace the requirements and docker-compose with their v8 counterparts to complete the deployment.

**All the next steps are run in the `dev_server_pre` container.**

## 3. Update the Major topics to the new Topics

To ensure more consistency among all topics, a new list will be used. These will all be placed in the system as **NewTopics** vs the old **Topics**. This is done in the migration scripts, where the new topics will be added.

The NewTopics are assigned based on url keywords, which are retrieved from the URL of articles crawled. These are manually assigned into categories when they have been crawled more than 100 times. E.g. Kultur is associated with the new topic: "Culture & Art".

Currently, the new topics are all under new_topic and new tables to ensure the old topics are still kept. At some point, we can drop the old functionality, but we need to update all the **New** to be the default.

## 4. Collect the new URLs by using the **tools/es_v8_migration/set_url_keywords_article.py**

This will update create a mapping between articles and keyword topics and can be used to extract the most common keywords seen in the DB.

## 5. Link the URL discovered topics to the new topics

Here I will bootstrap it using the Lauritz model which does NLI to do Zero-Shot classification. We will only look at url topics with more than 100 articles. This needs to be a process that monitors the future, and alerts when there are new topics found.

If the keyword is not mapped to any topic then it's ignored when retrieving the topics for an article. Some words such as "News" are ignored and not even stored into the database. This list is kept in `url_keyword.py`

## 5.1. Run the **tools/es_v8_migration/set_topic_mapping_to_keywords.py**

This has been done for the keywords in the test database, with the proposed links listed in: **url_topics_count_with_pred_to_db.csv**

## 5.2. Run the **tools/es_v8_migration/set_new_topics_from_url_keyword.py**

With the topics linked to their keywords we can now create a mapping for all articles based on the keywords found in the URL. If none are found, they are left empty.

## 6. Run the tools/mysql_to_elastic_new_topics.py to re-index all the documents.

**NOTE:** We should index all the articles with topics either from URL or Hardset, before adding others. This ensures that the KNN voting has the maximum available pool of topics to vote from when doing inferance.

This will take sometime to run, with 5000 documents taking about: 1h08m in my laptop to index.

## 7. Enable the Feature Tag and visualize the differences in the Front-End
