
#import user/pass from .env file
include .env
export

# Define variables
SQL_FILE := zeeguu-anonymized-zeeguu_test-202401300908.sql
DOCKER_CONTAINER := zeeguu-mysql


# Define targets
.PHONY: populatedb run shell test cleanup clearDB

#Rebuilds all docker images for you 
init:
	@echo "Building all docker images"
	@docker build -f Dockerfile.development -t zeeguu_api_dev .
	@docker run --name=$(DOCKER_CONTAINER) -p 8080:3306 -d zeeguu/${DOCKER_CONTAINER}
	
#this looks for a file called zeeguu-anonymized-zeeguu_test-202401300908.sql and copies it to the mysql container and runs it
#Make sure you have it locally 
populatedb: 
	@echo "Populating the database, this will take a while ⌛⌛⌛⌛"
	@Using "$(SQL_FILE)" to populate the database
	@docker cp $(SQL_FILE) $(DOCKER_CONTAINER):/$(SQL_FILE)
	@docker exec -i $(DOCKER_CONTAINER) bash -c ' \
		mysql -u $(MYSQL_USER) -p$(MYSQL_PASSWORD) zeeguu_test < /$(SQL_FILE);


shell:
	@docker exec -it $(DOCKER_CONTAINER) /bin/bash

#Runs the two compose targets for local development
run:
	@echo "Running compose functions"
	@docker-compose up dev_play
	@docker-compose up dev_server

#Run the tests
test:
	@echo "Running the tests"
	@sh run_tests.sh

cleanup: 
	@echo "cleaning up"
	@CONTAINER_IDS=$$(docker ps -a --filter "name=api" --format "{{.ID}}"); \
    for CONTAINER_ID in $$CONTAINER_IDS; do \
        if [ ! -z "$$CONTAINER_ID" ]; then \
            docker rm -f -v $$CONTAINER_ID; \
        fi \
    done
	@CONTAINER_ID=$$(docker ps -a --filter "ancestor=zeeguu/zeeguu-mysql" --format "{{.ID}}" | head -n 1); \
    if [ ! -z "$$CONTAINER_ID" ]; then \
        docker rm -f -v $$CONTAINER_ID; \
    fi

clearDB:
	@echo "running dbCleanup"
	@CONTAINER_ID=$$(docker ps -a --filter "ancestor=zeeguu/zeeguu-mysql" --format "{{.ID}}" | head -n 1); \
    if [ ! -z "$$CONTAINER_ID" ]; then \
        docker rm -f -v $$CONTAINER_ID; \
    fi
	@VOLUME_NAME=$$(docker volume ls -q --filter="name=local"); \
    if [ ! -z "$$VOLUME_NAME" ]; then \
        docker volume rm $$VOLUME_NAME; \
    fi