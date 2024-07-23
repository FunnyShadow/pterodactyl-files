ARG IMAGE_BASE=azul/zulu-openjdk-debian
ARG JAVA
FROM ${IMAGE_BASE}:${JAVA}-latest

# Replacing the system image source
ARG REGION
COPY debian.${REGION}.sources /etc/apt/sources.list.d/debian.sources

# Initialize
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget libargon2-1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python 3.12 for MCDR
ARG TYPE
ARG PYTHON=3.12.3
ARG REGION
ENV PATH="/usr/local/bin:${PATH}"

RUN if [ "${TYPE}" = "mcdr" ]; then \
        buildDeps='build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev' && \
        apt-get update && \
        apt-get install -y --no-install-recommends $buildDeps && \
        cd /tmp && \
        if [ "${REGION}" = "china" ]; then \
            wget https://mirror.bjtu.edu.cn/python/${PYTHON}/Python-${PYTHON}.tgz; \
        else \
            wget https://www.python.org/ftp/python/${PYTHON}/Python-${PYTHON}.tgz; \
        fi && \
        tar -xzf Python-${PYTHON}.tgz && \
        cd Python-${PYTHON} && \
        ./configure --enable-optimizations && \
        make -j $(nproc) && \
        make install && \
        cd .. && \
        rm -rf Python-${PYTHON} Python-${PYTHON}.tgz && \
        apt-get purge -y --auto-remove $buildDeps && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        python3.12 --version; \
    fi

# Install MCDR and requirements
COPY requirements.txt /requirements.txt 
ARG MCDR_REQUIREMENT=mcdreforged

RUN if [ "${TYPE}" = "mcdr" ]; then \
        if [ "${REGION}" = "china" ]; then \
            python3.12 -m pip install --no-cache-dir -U pip -i https://mirrors.cernet.edu.cn/pypi/web/simple && \
            python3.12 -m pip install --no-cache-dir ${MCDR_REQUIREMENT} -r /requirements.txt -i https://mirrors.cernet.edu.cn/pypi/web/simple; \
        else \
            python3.12 -m pip install --no-cache-dir -U pip && \
            python3.12 -m pip install --no-cache-dir ${MCDR_REQUIREMENT} -r /requirements.txt; \
        fi && \
        rm -rf /requirements.txt; \
    fi

RUN useradd -d /home/container -m container
USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh /
CMD ["/bin/bash", "/entrypoint.sh"]