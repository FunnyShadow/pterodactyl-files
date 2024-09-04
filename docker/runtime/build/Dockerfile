# Base image selection
ARG IMAGE_BASE=azul/zulu-openjdk-debian
ARG JAVA=17
FROM ${IMAGE_BASE}:${JAVA}-latest AS base

# Build arguments
ARG REGION=global
ARG TYPE=vanilla
ARG PYTHON_VERSION=3.12.3
ARG MCDR_REQUIREMENT=mcdreforged

# Environment variables
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Copy custom source list if needed
COPY debian.${REGION}.sources /etc/apt/sources.list.d/debian.sources

# Install base dependencies
RUN apt-get update; \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        openssl \
        git \
        tar \
        sqlite3 \
        fontconfig \
        tzdata \
        iproute2 \
        gettext-base \
        wget \
        libargon2-1; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Python build stage (only if TYPE=mcdr)
FROM base AS python-builder
ARG REGION
ARG PYTHON_VERSION
ARG TYPE
RUN if [ "${TYPE}" = "mcdr" ]; then \
    # Install build dependencies
    buildDeps='build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev \
               libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev liblzma-dev'; \
    apt-get update; \
    apt-get install -y --no-install-recommends $buildDeps; \
    \
    # Download and compile Python
    cd /tmp; \
    wget -O Python-${PYTHON_VERSION}.tgz \
        $([ "${REGION}" = "china" ] && \
          echo "https://mirror.bjtu.edu.cn/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz" || \
          echo "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"); \
    tar -xzf Python-${PYTHON_VERSION}.tgz; \
    cd Python-${PYTHON_VERSION}; \
    ./configure --enable-optimizations --with-system-expat --with-system-ffi --with-ensurepip=yes; \
    make -j $(nproc); \
    make install; \
    \
    # Cleanup
    cd /; \
    rm -rf /tmp/Python-${PYTHON_VERSION}*; \
    apt-get purge -y --auto-remove $buildDeps; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    \
    # Verify Python installation
    python3 --version; \
    python3 -c "import lzma; print('lzma module is available')"; \
fi

# Final stage
FROM base
ARG TYPE
ARG REGION
ARG MCDR_REQUIREMENT

# Copy Python from builder stage if TYPE=mcdr
COPY --from=python-builder /usr/local /usr/local

# Install MCDR and requirements if TYPE=mcdr
COPY mcdr-requirements.txt /tmp/requirements.txt
RUN if [ "${TYPE}" = "mcdr" ]; then \
    # Upgrade pip and install requirements
    python3 -m pip install --no-cache-dir -U pip; \
    python3 -m pip install --no-cache-dir ${MCDR_REQUIREMENT} -r /tmp/requirements.txt \
        $([ "${REGION}" = "china" ] && echo "-i https://mirrors.cernet.edu.cn/pypi/web/simple"); \
    rm -rf /tmp/requirements.txt; \
fi

RUN useradd -d /home/container -m container
USER container

ENV USER=container HOME=/home/container
WORKDIR /home/container
COPY ./entrypoint.sh /entrypoint.sh

CMD ["/bin/bash", "/entrypoint.sh"]