ARG SYSTEM
ARG VERSION

FROM ${SYSTEM}:${VERSION}

ARG SYSTEM
ARG VERSION
ARG PYTHON_VERSION
RUN \
    if [ "${SYSTEM}" == "debian" ]; then \
        if [ "${VERSION}" == "bookworm" ]; then \
            sed \
            -i.bak \
            -e 's/deb.debian.org/mirrors.cernet.edu.cn/g' \
            /etc/apt/sources.list.d/debian.sources; \
        else \
            sed \ 
            -i.bak \
            -e 's/deb.debian.org/mirrors.ustc.edu.cn/g' \
            -e 's|security.debian.org/debian-security|mirrors.ustc.edu.cn/debian-security|g' \
            /etc/apt/sources.list; \
        fi; \
        apt-get update -y; \
        apt-get install -y -f curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev; \
        cd /tmp; \
        wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz; \
        tar -xzvf Python-${PYTHON_VERSION}.tgz; \
        cd Python-${PYTHON_VERSION}; \
        ./configure --enable-optimizations; \
        make -j 8; \
        make altinstall; \
        apt-get remove -y build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev; \
        apt-get autoremove -y; \
        apt-get clean; \
    fi

ARG SYSTEM
ARG VERSION
ARG PYTHON_VERSION
RUN \
    if [ "${SYSTEM}" == "rockylinux" ]; then \
        if [ "${VERSION}" == "8" ]; then \
            sed \
            -i.bak \
            -e 's|^mirrorlist=|#mirrorlist=|g' \
            -e 's|^#baseurl=http://dl.rockylinux.org/$contentdir|baseurl=https://mirrors.cernet.edu.cn/rocky|g' \
            /etc/yum.repos.d/Rocky-AppStream.repo \
            /etc/yum.repos.d/Rocky-BaseOS.repo \
            /etc/yum.repos.d/Rocky-Extras.repo \
            /etc/yum.repos.d/Rocky-PowerTools.repo; \
            dnf install 'dnf-command(config-manager)'; \
            dnf config-manager --set-enabled crb; \
        else \
            sed \
            -i.bak \
            -e 's|^mirrorlist=|#mirrorlist=|g' \
            -e 's|^#baseurl=http://dl.rockylinux.org/$contentdir|baseurl=https://mirrors.cernet.edu.cn/rocky|g' \
            /etc/yum.repos.d/rocky-extras.repo \
            /etc/yum.repos.d/rocky.repo; \
            dnf config-manager --set-enabled crb; \
        fi; \
        dnf makecache; \
        dnf install -y --allowerasing findutils curl ca-certificates openssl git tar sqlite fontconfig tzdata iproute gettext wget make gcc gcc-c++ ncurses-devel openssl-devel sqlite-devel tk-devel gdbm-devel glibc-devel bzip2-devel libffi-devel zlib-devel; \
        cd /tmp; \
        wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz; \
        tar -xzvf Python-${PYTHON_VERSION}.tgz; \
        cd Python-${PYTHON_VERSION}; \
        ./configure --enable-optimizations; \
        make -j 8; \
        make altinstall; \
        dnf remove -y findutils make gcc gcc-c++ ncurses-devel openssl-devel sqlite-devel tk-devel gdbm-devel glibc-devel bzip2-devel libffi-devel zlib-devel; \
        dnf autoremove -y; \
        dnf clean all; \
    fi

ARG PYTHON_VERSION
RUN \
    cd /tmp; \
    pip3 cache purge; \
    rm -rf /requirements.txt; \
    rm -rf /tmp/Python-${PYTHON_VERSION}; \
    rm -rf /tmp/Python-${PYTHON_VERSION}.tgz;

RUN useradd -d /home/container -m container;
USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh /
CMD ["/bin/bash", "/entrypoint.sh"]
