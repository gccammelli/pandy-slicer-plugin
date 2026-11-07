# Build environment for Pandy Studio's slicing engine. Bambu Studio 02.08.02.61 for Linux is built with
# GCC 13.3 on Ubuntu 24.04 (its binary says "GCC: (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0"), so the engine is built
# with that same compiler and C++ library, natively for x86-64 and with Ubuntu's matching cross compiler for arm64.
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential gcc-13 g++-13 gcc-13-aarch64-linux-gnu g++-13-aarch64-linux-gnu \
        libc6-dev-arm64-cross binutils-aarch64-linux-gnu \
        cmake ninja-build autoconf automake libtool m4 pkg-config file patch git ca-certificates curl \
        python3 perl texinfo gettext \
        libgl-dev libglu1-mesa-dev libegl-dev libglew-dev libglfw3-dev libwxgtk3.2-dev libgtk-3-dev libdbus-1-dev \
        libavcodec-dev libavutil-dev libswscale-dev libswresample-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libwebkit2gtk-4.1-dev libsecret-1-dev libudev-dev libosmesa6-dev libtiff-dev \
    && rm -rf /var/lib/apt/lists/*
# GUI headers above are only compiled against, never linked: the engine keeps the CLI's plate code (in the GUI
# sources) and traps every GUI symbol it does not need (see engine/README.md).
# wxWidgets' GTK port is compiled for arm64 against the GTK 3 headers above (the engine links no GTK: the phone has
# no display). They are architecture-independent except glib's glibconfig.h, taken from Ubuntu's arm64 package.
# OpenSSL and curl also come from Ubuntu's arm64 packages: upstream's recipe cannot cross-compile OpenSSL, and the
# engine only references them from the CLI's network code, which it never runs (traps).
RUN dpkg --add-architecture arm64 \
    && sed -i 's/^Types: deb$/Types: deb\nArchitectures: amd64/' /etc/apt/sources.list.d/ubuntu.sources \
    && printf 'Types: deb\nURIs: http://ports.ubuntu.com/ubuntu-ports\nSuites: noble noble-updates noble-security\nComponents: main universe\nArchitectures: arm64\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n' > /etc/apt/sources.list.d/ports.sources \
    && apt-get update && cd /tmp && apt-get download libglib2.0-dev:arm64 libssl-dev:arm64 libcurl4-openssl-dev:arm64 \
    && for d in *_arm64.deb; do dpkg -x $d /opt/arm64-glib; done && rm -f /tmp/*.deb && rm -rf /var/lib/apt/lists/* \
    && test -f /opt/arm64-glib/usr/lib/aarch64-linux-gnu/glib-2.0/include/glibconfig.h
# Unsuffixed cross tool names for the autotools recipes (they call <prefix>-gcc).
RUN for t in gcc g++ cpp gcc-ar gcc-nm gcc-ranlib; do ln -sf /usr/bin/aarch64-linux-gnu-$t-13 /usr/bin/aarch64-linux-gnu-$t; done
RUN gcc --version | head -1 && aarch64-linux-gnu-g++-13 --version | head -1
