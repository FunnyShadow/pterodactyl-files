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
        yum install -y curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget; \
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
        apt-get install -y -f curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget; \
        apt-get clean; \
    fi

RUN useradd -d /home/container -m container;
USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh /
CMD ["/bin/bash", "/entrypoint.sh"]
