FROM ubuntu:24.04 AS base

SHELL ["/bin/bash", "-c"]

ENV project=meeting-sdk-linux-sample
ENV cwd=/tmp/$project

WORKDIR $cwd

ARG DEBIAN_FRONTEND=noninteractive

#  Install Dependencies
RUN apt-get update  \
    && apt-get install -y \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    gdb \
    git \
    gfortran \
    libopencv-dev \
    libdbus-1-3 \
    libgbm1 \
    libgl1 \
    libglib2.0-0 \
    libglib2.0-dev \
    libssl-dev \
    libx11-dev \
    libx11-xcb1 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-xfixes0 \
    libxcb-xtest0 \
    libgl1-mesa-dri \
    libxfixes3 \
    libssl-dev \
    linux-libc-dev \
    pciutils \
    pkgconf \
    tar \
    unzip \
    xz-utils \
    zip

# Install ALSA
RUN apt-get install -y libasound2t64 libasound2-plugins alsa alsa-utils alsa-oss

# Install Pulseaudio
RUN apt-get install -y  pulseaudio pulseaudio-utils

FROM base AS deps

ENV TINI_VERSION=v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

WORKDIR /opt
RUN git clone --depth 1 https://github.com/Microsoft/vcpkg.git \
    && ./vcpkg/bootstrap-vcpkg.sh -disableMetrics \
    && ln -s /opt/vcpkg/vcpkg /usr/local/bin/vcpkg \
    && vcpkg install vcpkg-cmake

FROM deps AS build

# Ensure tini is available
COPY --from=deps /tini /tini
RUN chmod +x /tini

WORKDIR $cwd

# Set HOME environment variable early - Zoom SDK needs this for cache
ENV HOME=/root

# Create Zoom SDK cache directories and audio socket directory before anything else
RUN mkdir -p /root/.zoomsdk /root/.zoomus /root/.zoom /root/.config/zoomus /tmp/.zoomus /tmp/zoom /tmp/audio \
    && chmod -R 777 /root/.zoomsdk /root/.zoomus /root/.zoom /root/.config/zoomus /tmp/.zoomus /tmp/zoom /tmp/audio \
    && echo -e "[General]\nsystem.audio.type=default" > /root/.config/zoomus.conf

# Download and extract Zoom Meeting SDK from Supabase
RUN mkdir -p lib/zoomsdk \
    && curl -L --fail --show-error \
       "https://supabase.suimation.de/storage/v1/object/public/CoolifyInputs/zoom-meeting-sdk-linux_x86_64-6.6.10.8600.tar.xz" \
       -o /tmp/zoom-sdk.tar.xz \
    && xz -d /tmp/zoom-sdk.tar.xz \
    && tar -xf /tmp/zoom-sdk.tar -C lib/zoomsdk \
    && rm /tmp/zoom-sdk.tar \
    && ln -s libmeetingsdk.so lib/zoomsdk/libmeetingsdk.so.1 \
    && ls -la lib/zoomsdk/

# Copy source files
COPY . .

# Build the project
RUN cmake --preset release \
    && cmake --build --preset release

ENTRYPOINT ["/tini", "--", "./bin/entry.sh"]


