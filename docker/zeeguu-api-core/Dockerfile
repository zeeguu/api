FROM python:3.6

# Update and install additional tools
RUN apt-get update
RUN apt-get install vim -y

# Install Zeeguu-Core
WORKDIR /opt
RUN git clone https://github.com/zeeguu-ecosystem/Zeeguu-Core
WORKDIR /opt/Zeeguu-Core
RUN pip install -r requirements.txt
RUN python setup.py install

# Install Zeeguu-API
WORKDIR /opt
RUN git clone https://github.com/zeeguu-ecosystem/Zeeguu-API
WORKDIR /opt/Zeeguu-API
RUN pip install -r requirements.txt
RUN python setup.py install

# Set default path to config
ENV ZEEGUU_CORE_CONFIG=/opt/Zeeguu-Core/default_core.cfg
ENV ZEEGUU_API_CONFIG=/opt/Zeeguu-API/default_api.cfg
# RUN python -m zeeguu.populate

CMD ["python", "zeeguu_api"]
