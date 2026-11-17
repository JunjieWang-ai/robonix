# SPDX-License-Identifier: MulanPSL-2.0
# ROS 2 Jazzy + Webots (GUI) + Nav2 deps + Python deps for robonix
# drivers that get `docker exec`'d into this container by `rbnx boot`.
# This image is the SIM container; it does NOT contain robonix driver
# code. Driver code lives in each primitive/service package directory
# on the host and is bind-mounted in by compose.yaml under /robonix_pkgs.
# Build context = the directory containing this Dockerfile (sim/bridge/).
ARG ROS_BASE_IMAGE=osrf/ros:jazzy-desktop-full
FROM ${ROS_BASE_IMAGE}

# ── TUNA mirrors ───────────────────────────────────────────────────
# Swap apt sources (Ubuntu/ports + ROS 2) to TUNA. Use `find` + sed
# --follow-symlinks because /etc/apt/sources.list.d/ros2.sources is
# a symlink into /usr/share/ros-apt-source/ in the upstream ros image.
RUN set -eux; \
    find /etc/apt/sources.list.d/ -maxdepth 1 \( -name '*.list' -o -name '*.sources' \) -print0 \
      | xargs -0 -r sed -i --follow-symlinks \
          -e 's|http://packages\.ros\.org/ros2/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu|g' \
          -e 's|^Types: deb deb-src$|Types: deb|'; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i --follow-symlinks \
            -e 's|http://archive\.ubuntu\.com/ubuntu/\?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' \
            -e 's|http://security\.ubuntu\.com/ubuntu/\?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' \
            -e 's|http://ports\.ubuntu\.com/ubuntu-ports/\?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/|g' \
            /etc/apt/sources.list; \
    fi
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    HF_ENDPOINT=https://hf-mirror.com
ENV DEBIAN_FRONTEND=noninteractive

# xvfb / Xorg / mesa-utils / pciutils are needed by the headless display
# backends (`WEBOTS_HEADLESS_MODE` in entrypoint.sh). They are tiny and
# the legacy host-DISPLAY path doesn't use them, so keeping them always
# installed avoids a second image variant.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb-cursor0 \
    xvfb \
    xserver-xorg-core \
    mesa-utils \
    pciutils \
    python3-pip \
    python3-colcon-common-extensions \
    unzip \
    ros-jazzy-nav2-msgs \
    ros-jazzy-nav2-bringup \
    ros-jazzy-webots-ros2 \
    ros-jazzy-webots-ros2-driver \
    ros-jazzy-controller-manager \
    ros-jazzy-diagnostic-updater \
    ros-jazzy-diff-drive-controller \
    ros-jazzy-joint-state-broadcaster \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-tf2-ros \
    ros-jazzy-rmw-zenoh-cpp \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# tf2 (ros2/geometry2#982) and its ros2-testing workaround: NOT needed on
# Jazzy. The Humble-era hack pinned ros-humble-tf2* from the ros2-testing
# repo to dodge a tf2 0.25.23 deadlock (rviz2 in this container stopped
# responding a few minutes into mapping). Jazzy ships tf2 0.36.x where the
# deadlock is long fixed, and this block is a guaranteed build failure on
# noble anyway: dpkg-query resolves no ros-jazzy-tf2* packages from the
# hack's own pattern, so dpkg --compare-versions "" ge 0.25.24 fails under
# set -e. The same block also existed in the service-map/service-navigation
# upstream images, which drop it in the same change.

# Webots simulator (Cyberbotics .deb; apt "webots" is often unavailable on minimal images)
# Match ros-jazzy-webots-ros2 (2025.0.0) — see https://github.com/cyberbotics/webots/releases
# Default URL uses ghfast.top mirror for reliable access; override with
# --build-arg WEBOTS_DEB_URL=https://github.com/... for direct GitHub.
ARG WEBOTS_DEB_URL=https://ghfast.top/https://github.com/cyberbotics/webots/releases/download/R2025a/webots_2025a_amd64.deb
RUN set -eux; \
    wget -S --progress=dot:giga -O /tmp/webots.deb "${WEBOTS_DEB_URL}"; \
    ls -lh /tmp/webots.deb; \
    apt-get update; \
    apt-get install -y --no-install-recommends /tmp/webots.deb; \
    rm -f /tmp/webots.deb; \
    rm -rf /var/lib/apt/lists/*

# Keep the remote viewer in read-only W3D broadcast mode. The public stream
# port is injected by viewer_server.py at runtime so custom ports work with
# both host and bridge networking. Webots' raw stream remains on port 1234.
RUN sed -i \
      -e 's#https://cyberbotics.com/wwi/R2025a/WebotsView.js#/wwi-full/WebotsView.js#' \
      -e 's#</body>#<script>const wsPort=new URLSearchParams(location.search).get("wsPort")||"__WEBOTS_STREAM_PORT__";document.getElementById("IP-input").value="ws://"+location.hostname+":"+wsPort;document.getElementById("mode").value="w3d";document.getElementById("broadcast").checked=true;</script></body>#' \
    /usr/local/webots/resources/web/streaming_viewer/index.html

# Python deps used by the robonix driver processes that will be `docker
# exec`'d into this container. (Drivers themselves live on host; their
# Python imports resolve against this image's site-packages + the
# bind-mounted package dirs under /robonix_pkgs.)
ENV PIP_BREAK_SYSTEM_PACKAGES=1
# Ubuntu 22.04 ships pip 22.0.x, whose resolver hits a known AssertionError
# (get_topological_weights, fixed in pip 22.1) on dependency cycles. fastmcp
# 3.4.7 introduced such a cycle via fastmcp-slim -> py-key-value-aio ->
# keyring, so the stock pip must be upgraded before the real install.
# Exact pins: this image exists for CI, and an open range here means any
# upstream release can break every run overnight, as fastmcp 3.4.7 did.
# Bump the set deliberately, in its own commit.
# (noble's apt pip 24.0 is modern; do NOT `pip install --upgrade pip` here —
# pip cannot uninstall the Debian-owned pip and the build fails with
# "Cannot uninstall pip 24.0, RECORD file not found".)
RUN python3 -m pip install --no-cache-dir \
    "grpcio==1.80.0" "protobuf==6.33.6" "mcp==1.29.0" "fastmcp==3.4.7" \
    numpy Pillow "uvicorn==0.52.3" "httpx==0.28.1" "websockets==16.1.1"

ENV RMW_IMPLEMENTATION=rmw_zenoh_cpp

# Build context is sim/bridge/ — ros_ws lives one level up at sim/ros_ws/.
# Compose passes context: ../ so we COPY from there.
WORKDIR /colcon_ws
COPY ros_ws/src/eaios_webots src/eaios_webots
RUN bash -lc "source /opt/ros/$ROS_DISTRO/setup.bash && colcon build --symlink-install --packages-select eaios_webots"

COPY bridge/entrypoint.sh /entrypoint.sh
COPY bridge/viewer_server.py /viewer_server.py
COPY bridge/webots_stream_proxy.py /webots_stream_proxy.py
COPY bridge/streaming_healthcheck.py /streaming_healthcheck.py
RUN chmod +x /entrypoint.sh /viewer_server.py /webots_stream_proxy.py /streaming_healthcheck.py

WORKDIR /
ENTRYPOINT ["/entrypoint.sh"]
