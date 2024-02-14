# How to run:

### 1.

Run this command in WSL while having docker desktop up.

``docker build -f Dockerfile.development -t zeeguu_api_dev .``

### 2.

Run this after to create the container

``docker run --name=zeeguu-mysql -p 8080:3306 -d zeeguu/zeeguu-mysql``

### 3.

Run this command to populate the database

``docker-compose up dev_play``

### 4.

Run this to run the server

``docker-compose up dev_server``

Go to this URL to check that the server is running

``http://localhost:9001/available_languages``

Should get an input similar to

``["de", "es", "fr", "nl", "en", "it", "da", "pl", "sv", "ru", "no", "hu", "pt"]``

# Back for database if makefile does not work

````

docker cp zeeguu-anonymized-zeeguu_test-202401300908.sql zeeguu-mysql:zeeguu-anonymized-zeeguu_test-202401300908.sql

docker exec -it zeeguu-mysql /bin/bash

mysql -u zeeguu_test -p zeeguu_test

USE zeeguu_test

source zeeguu-anonymized-zeeguu_test-202401300908.sql

````
# ER-diagram

![mermaid-diagram-2024-02-13-173125](https://github.com/Mlth/zeeguu-api/assets/94927866/6dfad407-fe9f-4cd0-ac91-a232fa4754c2)

![mermaid](https://t.ly/PYen4)
<img src="https://t.ly/PYen4">



