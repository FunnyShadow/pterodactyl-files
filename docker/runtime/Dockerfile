ARG IMAGE_BASE=azul/zulu-openjdk-debian
ARG JAVA
FROM ${IMAGE_BASE}:${JAVA}-latest

# Replacing the system image source
ARG REGION
COPY debian.${REGION}.sources /etc/apt/sources.list.d/debian.sources

# Initialize
RUN \
    apt-get update; \
    apt-get install -y -f curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget libargon2-1;

# Install Python 3.12 for MCDR
ARG TYPE, REGION
ARG PYTHON=3.12.3
RUN if [ "${TYPE}" = "mcdr" ]; then \
        apt-get install -y build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev; \
        cd /tmp; \
        [ ${REGION} =="china" ] && wget https://mirror.bjtu.edu.cn/python/${PYTHON}/Python-${PYTHON}.tgz; \
        [ ${REGION} =="global" ] && wget https://www.python.org/ftp/python/${PYTHON}/Python-${PYTHON}.tgz; \
        tar -xzvf Python-${PYTHON}.tgz; \
        cd Python-${PYTHON}; \
        ./configure --enable-optimizations; \
        make -j 8; \
        make altinstall; \
    fi;

# Install MCDR and requirements
COPY requirements.txt /requirements.txt 
ARG TYPE
ARG MCDR_REQUIREMENT=mcdreforged
RUN if [ "${TYPE}" = "mcdr" ]; then \
        if [ "${REGION}" = "china" ]; then \
            python3.12 -m pip install -U pip -i https://mirrors.cernet.edu.cn/pypi/web/simple; \
            python3.12 -m pip install ${MCDR_REQUIREMENT} -i https://mirrors.cernet.edu.cn/pypi/web/simple; \
            python3.12 -m pip install -r /requirements.txt -i https://mirrors.cernet.edu.cn/pypi/web/simple; \
        else; \
            python3.12 -m pip install -U pip; \
            python3.12 -m pip install ${MCDR_REQUIREMENT}; \
            python3.12 -m pip install -r /requirements.txt; \
        fi; \
    fi;

# Clean up
ARG TYPE
RUN if [ "${TYPE}" = "mcdr" ]; then \
        cd /tmp; \
        python3.12 -m pip cache purge; \
        rm -rf /requirements.txt; \
        rm -rf /tmp/Python-${PYTHON}; \
        rm -rf /tmp/Python-${PYTHON}.tgz; \
        apt-get remove -y build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev; \
    fi;
RUN \
    apt-get autoremove -y; \
    apt-get clean;

RUN useradd -d /home/container -m container;
USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh /
CMD ["/bin/bash", "/entrypoint.sh"]
