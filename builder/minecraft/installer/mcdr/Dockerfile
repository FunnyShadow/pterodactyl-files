FROM debian:stable-slim

RUN sed -i.bak 's/deb.debian.org/mirrors.cernet.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i.bak 's|security.debian.org/debian-security|mirrors.cernet.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update -y \
    && apt-get install -y \
    && apt-get install -y python3 python3-pip \
    && python3 -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple --break-system-packages \
    && python3 -m pip install mcdreforged -i https://pypi.tuna.tsinghua.edu.cn/simple --break-system-packages