FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    openjdk-17-jdk maven python3 python3-pip python3-venv git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /yaoki
COPY . /yaoki

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r analysis/requirements.txt \
    && /opt/venv/bin/pip install jupyterlab ipykernel \
    && /opt/venv/bin/python -m ipykernel install \
        --name yaoki \
        --display-name "Python (YAOKI)" \
        --sys-prefix

RUN ./data/setup_yamcs_data.sh

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

EXPOSE 8090 8888

CMD bash -lc 'cd /yaoki/yamcs-server && mvn yamcs:run & \
    /opt/venv/bin/jupyter lab \
      --ip=0.0.0.0 \
      --port=8888 \
      --no-browser \
      --allow-root \
      --NotebookApp.token="" & \
    until curl -sf http://localhost:8888/lab; do sleep 1; done && \
    until curl -sf http://localhost:8090; do sleep 1; done && \
    touch /ready && \
    wait'
