

#Rebuilds all docker images for you 
init:
	@echo "Building all docker images"
	@docker build -f Dockerfile.development -t zeeguu_api_dev .
	@docker run --name=zeeguu-mysql -p 8080:3306 -d zeeguu/zeeguu-mysql


#Runs the two compose targets for local development
run:
	@echo "Running compose functions"
	@docker-compose up dev_play
	@docker-compose up dev_server

#Run the tests
test:
	@echo "Running the tests"
	@sh run_tests.sh

