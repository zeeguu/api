# Update to Topics

## 1. Update ElasticSearch to 8.\*

The first step is to update ES, as it supports KNN searches with dense vectors which will be used in the new way of classifying topics.

### 1.1. Update docker-compose with a new service that corresponds to the new version

I provided this under **elasticsearch_v8** in this codebase. We also need to set the `xpack.security.enabled=false` to allow us to connect via HTTP, otherwise we would need to set an SSL key.

## 2. Create the API to provide the article embedding service.

I have created a folder for a small flask API application which will be in charge of embedding documents into dense vectors.
In the semanticEmbApi, it's include a dockerfile to create the image for this flask application, as well as the basic interface for a **semantic_vector** generator. In this case, we are using https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2 which has been downloaded into the binaries folder to avoid having to download it late.

### 2.1. Include this service within the docker-compose file and include the connection string in the images to allow them to connect to the model.

Within the `zeeguu.core` folder, we can find a new folder `semantic_vector_api`, which will include the logic to retrieve the dense vector given a document's content.

NOTE: We might want more methods for embedding a sentence for instance.

## 3. Update the Major topics to the new Topics

To ensure more consistency among all topics, a new list will be used. We need to make sure that the old topics map to the new, and maybe we phase some of them out?

Currently, the new topics are all under new_topic and new tables to ensure the old topics are still kept. At some point, we will have to renamed them to be the main and we can rename the old tables to legacy.

## 4. Collect the new URLs by using the **tools/set_topic_keywords_article.py**

This will update create a mapping between articles and keyword topics and can be used to extract the most common keywords seen in the DB.

## 5. Link the URL discovered topics to the new topics

Here I will bootstrap it using the Lauritz model which does NLI to do Zero-Shot classification. We will only look at url topics with more than 100 articles. This needs to be a process that monitors the future, and alerts when there are new topics found.

If the keyword is not mapped to any topic then it's ignored when retrieving the topics for an article. For instance: "News" can be an ignored keyword with no mapping.

## 5.1. Run the **tools/set_topic_from_url_article.py**

With the topics linked to their keywords we can now create a mapping for all articles based on the keywords found in the URL. If none are found, they are left empty.

## 6. Run the tools/mysql_to_elastic.py to re-index all the documents.

This will take sometime to run, with 5000 taking about: 1h08m in my laptop.

## 7. Make sure the code takes the new changes and visualizes them correctly in the front-end.
