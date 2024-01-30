

# How to run:

### 1. 
Run this command in WSL while having docker desktop up.

`` docker build -f Dockerfile.development -t zeeguu_api_dev . ``


### 2. 
Run this after to create the container

`` docker run --name=zeeguu-mysql -p 8080:3306 -d zeeguu/zeeguu-mysql `` 

### 3.
Run this command to populate the database

`` docker-compose up dev_play ``

### 4.
Run this to run the server

`` docker-compose up dev_server ``

Go to this URL to check that the server is running

`` http://localhost:9001/available_languages ``

Should get an input similar to 

`` ["de", "es", "fr", "nl", "en", "it", "da", "pl", "sv", "ru", "no", "hu", "pt"] ``
