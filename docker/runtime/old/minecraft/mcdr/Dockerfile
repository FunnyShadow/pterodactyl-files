ARG SYSTEM
ARG JAVA_VERSION

FROM azul/zulu-openjdk-${SYSTEM}:${JAVA_VERSION}-latest

ARG SYSTEM
RUN \
    if [ "${SYSTEM}" == "centos" ]; then \
        sed \
        -i.bak \
        -e 's|^mirrorlist=|#mirrorlist=|g' \
        -e 's|^#baseurl=http://mirror.centos.org/centos|baseurl=https://mirrors.cernet.edu.cn/centos|g' \ 
        /etc/yum.repos.d/CentOS-*.repo; \
        yum update -y; \
        yum install -y curl ca-certificates openssl git tar sqlite fontconfig tzdata iproute gettext wget make gcc gcc-c++ ncurses-devel openssl-devel sqlite-devel tk-devel gdbm-devel glibc-devel bzip2-devel libffi-devel zlib-devel; \
        cd /tmp; \
        wget https://www.python.org/ftp/python/3.11.8/Python-3.11.8.tgz; \
        tar -xzvf Python-3.11.8.tgz; \
        cd Python-3.11.8; \
        ./configure --enable-optimizations; \
        make -j 8; \
        make altinstall; \
        yum remove -y make gcc gcc-c++ ncurses-devel openssl-devel sqlite-devel tk-devel gdbm-devel glibc-devel bzip2-devel libffi-devel zlib-devel; \
        yum autoremove -y; \
        yum clean all; \
    fi

ARG SYSTEM
RUN \
    if [ "${SYSTEM}" == "debian" ]; then \
        sed \
        -i.bak \
        -e 's/deb.debian.org/mirrors.cernet.edu.cn/g' \
        -e 's|security.debian.org/debian-security|mirrors.cernet.edu.cn/debian-security|g' \
        /etc/apt/sources.list; \
        apt-get update -y; \
        apt-get install -y -f curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev; \
        cd /tmp; \
        wget https://www.python.org/ftp/python/3.11.8/Python-3.11.8.tgz; \
        tar -xzvf Python-3.11.8.tgz; \
        cd Python-3.11.8; \
        ./configure --enable-optimizations; \
        make -j 8; \
        make altinstall; \
        apt-get remove -y build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev; \
        apt-get autoremove -y; \
        apt-get clean; \
    fi

ARG MCDR_REQUIREMENT
COPY requirements.txt /requirements.txt
RUN \
    python3.11 -m ensurepip; \
    python3.11 -m pip install -U pip; \
    python3.11 -m pip install ruamel.yaml; \
    python3.11 -m pip install -r /requirements.txt; \
    python3.11 -m pip install -U ${MCDR_REQUIREMENT}; \
    cd /tmp; \
    pip3 cache purge; \
    rm -rf /requirements.txt; \
    rm -rf /tmp/Python-3.11.8; \
    rm -rf /tmp/Python-3.11.8.tgz;

RUN useradd -d /home/container -m container;
USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh /
CMD ["/bin/bash", "/entrypoint.sh"]
