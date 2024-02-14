ARG SYSTEM=debian
ARG JAVA_VERSION=19
FROM azul/zulu-openjdk-${SYSTEM}:${JAVA_VERSION}-latest

RUN sed -i.bak 's/deb.debian.org/mirrors.cernet.edu.cn/g' /etc/apt/sources.list \
    && sed -i.bak 's|security.debian.org/debian-security|mirrors.cernet.edu.cn/debian-security|g' /etc/apt/sources.list \
    && apt-get update -y \
    && apt-get install -y curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev \
    && cd /tmp \
    && wget https://www.python.org/ftp/python/3.11.8/Python-3.11.8.tgz \
    && tar -xzvf Python-3.11.8.tgz \
    && cd Python-3.11.8 \
    && ./configure --enable-optimizations \
    && make -j 8 \
    && make install \
    && apt-get remove -y build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && useradd -d /home/container -m container
    
ARG MCDR_REQUIREMENT=mcdreforged
COPY requirements.txt /requirements.txt
RUN python3 -m pip install -U pip \
    && pip3 install ruamel.yaml \
    && pip3 install -r /requirements.txt \
    && pip3 cache purge

RUN pip3 install -U ${MCDR_REQUIREMENT} \
    && pip3 cache purge

USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh ./start_hook.py ./start_hook.yml /
CMD ["/bin/bash", "/entrypoint.sh"]
