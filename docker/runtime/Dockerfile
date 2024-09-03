ARG IMAGE_BASE=azul/zulu-openjdk-debian
ARG JAVA
FROM ${IMAGE_BASE}:${JAVA}-latest

# Arguments
ARG REGION
ARG TYPE
ARG PYTHON=3.12.3
ARG MCDR_REQUIREMENT=mcdreforged

# Environment variables
ENV PATH="/usr/local/bin:${PATH}"

# Copy source list
COPY debian.${REGION}.sources /etc/apt/sources.list.d/debian.sources

# Install base dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates openssl git tar sqlite3 fontconfig tzdata \
        iproute2 gettext-base wget libargon2-1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python and MCDR if TYPE is mcdr
RUN if [ "${TYPE}" = "mcdr" ]; then \
    # Install build dependencies
    buildDeps='build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev \
               libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev liblzma-dev' && \
    apt-get update && \
    apt-get install -y --no-install-recommends $buildDeps && \
    \
    # Download and compile Python
    cd /tmp && \
    wget -O Python-${PYTHON}.tgz \
        $([ "${REGION}" = "china" ] && \
          echo "https://mirror.bjtu.edu.cn/python/${PYTHON}/Python-${PYTHON}.tgz" || \
          echo "https://www.python.org/ftp/python/${PYTHON}/Python-${PYTHON}.tgz") && \
    tar -xzf Python-${PYTHON}.tgz && \
    cd Python-${PYTHON} && \
    ./configure --enable-optimizations --with-system-expat --with-system-ffi --with-ensurepip=yes && \
    make -j $(nproc) && \
    make install && \
    cd .. && \
    rm -rf Python-${PYTHON} Python-${PYTHON}.tgz && \
    \
    # Verify Python installation
    python3.12 --version && \
    python3.12 -c "import lzma; print('lzma module is available')" && \
    \
    # Clean up
    apt-get purge -y --auto-remove $buildDeps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*; \
fi

# Copy requirements and install MCDR if TYPE is mcdr
COPY requirements.txt /requirements.txt
RUN if [ "${TYPE}" = "mcdr" ]; then \
    python3.12 -m pip install --no-cache-dir -U pip \
        $([ "${REGION}" = "china" ] && echo "-i https://mirrors.cernet.edu.cn/pypi/web/simple") && \
    python3.12 -m pip install --no-cache-dir ${MCDR_REQUIREMENT} -r /requirements.txt \
        $([ "${REGION}" = "china" ] && echo "-i https://mirrors.cernet.edu.cn/pypi/web/simple") && \
    rm -rf /requirements.txt; \
fi

# Set working directory
WORKDIR /workspace

# Uncomment the following lines if you need to set up for Pterodactyl
# RUN useradd -d /home/container -m container
# USER container
# ENV USER=container HOME=/home/container
# WORKDIR /home/container
# COPY ./entrypoint.sh /
# CMD ["/bin/bash", "/entrypoint.sh"]
