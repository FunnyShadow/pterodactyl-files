ARG SYSTEM=debian
ARG JAVA_VERSION=19
FROM azul/zulu-openjdk-${SYSTEM}:${JAVA_VERSION}-latest

RUN if [ "$SYSTEM" == "debian" ]; then \
    sed -i.bak 's/deb.debian.org/mirrors.cernet.edu.cn/g' /etc/apt/sources.list \
    && sed -i.bak 's|security.debian.org/debian-security|mirrors.cernet.edu.cn/debian-security|g' /etc/apt/sources.list \
    && apt-get update -y \
    && apt-get install -y curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget \
    ;fi

RUN if [ "$SYSTEM" == "centos" ]; then \
    sed -i.bak 's/deb.debian.org/mirrors.cernet.edu.cn/g' /etc/yum.repos.d/CentOS-Base.repo \
    && sed -i.bak 's|security.debian.org/debian-security|mirrors.cernet.edu.cn/debian-security|g' /etc/yum.repos.d/CentOS-Base.repo \
    && yum update -y \
    && yum install -y curl ca-certificates openssl git tar sqlite3 fontconfig tzdata iproute2 gettext-base wget \
    ;fi

USER container
ENV USER=container HOME=/home/container

WORKDIR /home/container
COPY ./entrypoint.sh /
CMD ["/bin/bash", "/entrypoint.sh"]
