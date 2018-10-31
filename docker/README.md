# Zeeguu container images

Prebuilt images are already available on [dockerhub](https://hub.docker.com/u/zeeguu).

### Building manually

To build the images, you need to have docker. Install it with:

```sh
sudo apt-get install docker.io -y
```

To build the zeeguu-mysql container:
```sh
cd zeeguu-mysql
docker build -t zeeguu-mysql .
```

To build the zeeguu-api-core container:
```sh
cd zeeguu-api-core
docker build -t zeeguu-api-core .
```
