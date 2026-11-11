# Orca 2.5.0's Ubuntu 24.04 release reports Clang/LLD 18.1.3 and GCC 14.2.0
# in its ELF .comment section. Keep this separate from Bambu's GCC 13 image.
FROM pandy-studio-build
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    clang-18 lld-18 g++-14 g++-14-aarch64-linux-gnu \
    && rm -rf /var/lib/apt/lists/*
# Orca links Ubuntu's libexpat on Linux (it never uses its bundled copy there): the arm64 engine takes the same
# package version for arm64, next to OpenSSL and curl.
RUN apt-get update && cd /tmp && apt-get download libexpat1-dev:arm64 \
    && for d in *_arm64.deb; do dpkg -x $d /opt/arm64-glib; done && rm -f /tmp/*.deb && rm -rf /var/lib/apt/lists/* \
    && test -f /opt/arm64-glib/usr/lib/aarch64-linux-gnu/libexpat.a
RUN clang++-18 --version && g++-14 --version && aarch64-linux-gnu-g++-14 --version
