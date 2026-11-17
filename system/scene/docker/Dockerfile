# SPDX-License-Identifier: MulanPSL-2.0
# system/scene container — ROS 2 base + scene's Python deps.
#
# Why scene gets its own image (and isn't, say, exec'd into the
# webots sim container): scene is a system service that should be
# robot-agnostic. Pinning it to the webots Dockerfile would make
# every soma's container have to bundle scene's deps. Separate image
# keeps coupling minimal — scene only needs to share the host DDS
# bus, which `--network host` gives us regardless of where the sim
# is running.
#
# ROS distro is NOT hard-pinned: Robonix does not bind to a single ROS
# release. Pick it with the `ROS_DISTRO` build arg (default `jazzy`); the
# base image, the `ros-<distro>-*` apt packages, and the runtime
# `source /opt/ros/<distro>/setup.bash` all follow it. Supported distros
# (tf2 + rmw-zenoh available in the index): humble (zenoh-bridge-dds also
# available), jazzy (noble index has no zenoh-bridge-dds — the vendor +
# security-tools pair from the same zenoh release replaces it). Set it with
# `ROBONIX_SCENE_ROS_DISTRO=jazzy rbnx build -p system/scene` (build.sh wires
# the env var to this build arg) — see the scene README "ROS distro" section.
#
# Layout inside the image:
#   /opt/ros/$ROS_DISTRO/...  ROS 2 (from base; $ROS_DISTRO set by the base)
#   /scene                    package dir, bind-mounted at runtime
#                             (so live edits don't need image rebuild)
#   /entrypoint.sh            sources ros + execs scene_service.service
#
# The image is built on demand by `bash system/scene/scripts/build.sh`
# the first time, then reused. Rebuild only when this Dockerfile or
# requirements/ change.

# Selects the ROS package names + runtime setup.bash path. build.sh also passes
# ROS_BASE_IMAGE, defaulting to a local robonix-ros:<distro>-ros-base alias so
# BuildKit does not query Docker Hub metadata on every rebuild. Override with
# ROBONIX_SCENE_ROS_BASE_IMAGE for a mirror, digest-pinned base, or custom image.
ARG ROS_DISTRO=jazzy
ARG ROS_BASE_IMAGE=robonix-ros:jazzy-ros-base
FROM ${ROS_BASE_IMAGE}

# noble (24.04) marks the system Python as externally managed (PEP 668);
# humble's 22.04 did not. Without this the bare pip installs below fail
# with "externally-managed-environment". (Same ENV as the webots sim image.)
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# ── Build-time proxy helpers ──────────────────────────────────────
# Usage:
#   - apt / pip: use `without-proxy ...`
#   - git / HuggingFace / OpenAI CDN: use `with-build-proxy ...`
#
# Note:
#   HTTP_PROXY_HOST / HTTPS_PROXY_HOST / NO_PROXY_HOST are declared later,
#   just before the first proxy-needed layer, so changing proxy args does
#   not invalidate earlier apt/pip layers.
RUN cat > /usr/local/bin/with-build-proxy <<'EOF' \
 && chmod +x /usr/local/bin/with-build-proxy \
 && cat > /usr/local/bin/without-proxy <<'EOF2' \
 && chmod +x /usr/local/bin/without-proxy
#!/usr/bin/env sh
set -eu

export HTTP_PROXY="${HTTP_PROXY_HOST:-}"
export HTTPS_PROXY="${HTTPS_PROXY_HOST:-}"
export http_proxy="${HTTP_PROXY_HOST:-}"
export https_proxy="${HTTPS_PROXY_HOST:-}"
export NO_PROXY="${NO_PROXY_HOST:-}"
export no_proxy="${NO_PROXY_HOST:-}"

exec "$@"
EOF
#!/usr/bin/env sh
set -eu

unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
unset ALL_PROXY all_proxy NO_PROXY no_proxy

exec "$@"
EOF2

# ── TUNA mirrors ───────────────────────────────────────────────────
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

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages we need at runtime.
# apt: do NOT use proxy; we already switched to TUNA mirrors.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    without-proxy sh -c ' \
        apt-get update && \
        apt-get install -y --no-install-recommends \
            python3-pip \
            ros-$ROS_DISTRO-cv-bridge \
            python3-numpy \
            ros-$ROS_DISTRO-tf2-ros \
            ros-$ROS_DISTRO-tf-transformations \
            ros-$ROS_DISTRO-rmw-cyclonedds-cpp \
            ros-$ROS_DISTRO-rmw-zenoh-cpp \
            $( [ "$ROS_DISTRO" = humble ] && echo "ros-$ROS_DISTRO-zenoh-bridge-dds" \
                                         || echo "ros-$ROS_DISTRO-zenoh-cpp-vendor ros-$ROS_DISTRO-zenoh-security-tools" ) && \
        rm -rf /var/lib/apt/lists/* \
    '

# pip: do NOT use proxy. noble's apt pip 24.0 is modern enough — do NOT
# `pip install --upgrade pip` here: pip cannot uninstall the Debian-owned
# pip (no RECORD file: "Cannot uninstall pip 24.0, RECORD file not found"),
# so that step is a guaranteed build failure on noble.

# torch + torchvision — sm_120 (Blackwell / RTX 5090) requires
# torch 2.7+ with CUDA 12.8 kernels. cu124 wheels only cover up to
# sm_90 and will fail with "no kernel image" on Blackwell.
# Aliyun mirror carries cu128 wheels; fall back to upstream PyTorch index.
# torch / torchvision cu128 only live on the aliyun pytorch-wheels mirror
# (TUNA has no cu128), so curl those two big wheels from aliyun — curl's
# -C - (resume) + --retry saturates the link (~11 MB/s), whereas pip's
# downloader does NOT resume and dies in an infinite restart loop when the
# aliyun mirror stalls a ~1 GB transfer partway. The nvidia-* deps are then
# resolved by pip from the default PIP_INDEX_URL (TUNA, set above) — do NOT
# point pip at aliyun's pypi index here, its large-file throttling stalls
# pip the same way.
# The saved filenames MUST be the canonical wheel names (pip parses the
# name/version/abi from the filename and rejects e.g. "torch.whl" with
# "Invalid wheel filename"), which would silently drop every build into
# the slow fallback below after wasting the full aliyun download.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    without-proxy sh -c 'set -eu; \
        PYTAG="cp$(python3 --version 2>&1 | sed "s/Python \([0-9]*\)\.\([0-9]*\).*/\1\2/")"; \
        base="https://mirrors.aliyun.com/pytorch-wheels/cu128"; \
        tw="torch-2.7.1+cu128-${PYTAG}-${PYTAG}-manylinux_2_28_x86_64.whl"; \
        tvw="torchvision-0.22.1+cu128-${PYTAG}-${PYTAG}-manylinux_2_28_x86_64.whl"; \
        curl -fSL --retry 5 --retry-delay 2 -C - -o "/tmp/$tw" \
             "$base/torch-2.7.1%2Bcu128-${PYTAG}-${PYTAG}-manylinux_2_28_x86_64.whl"; \
        curl -fSL --retry 5 --retry-delay 2 -C - -o "/tmp/$tvw" \
             "$base/torchvision-0.22.1%2Bcu128-${PYTAG}-${PYTAG}-manylinux_2_28_x86_64.whl"; \
        python3 -m pip install --progress-bar on --timeout 60 --retries 3 \
             "/tmp/$tw" "/tmp/$tvw"; \
        rm -f "/tmp/$tw" "/tmp/$tvw"' \
    || with-build-proxy python3 -m pip install \
        --progress-bar on \
        --timeout 60 \
        --retries 3 \
        --index-url https://download.pytorch.org/whl/cu128 \
        torch==2.7.1 torchvision==0.22.1

# Generic scene deps + concept-graphs perception stack.
# pip: do NOT use proxy; use PIP_INDEX_URL=TUNA.

# base
COPY requirements/scene-base.txt /tmp/requirements/scene-base.txt
# "numpy<2": noble's apt python3-numpy (1.26.4) is Debian-owned (no RECORD) —
# pip cannot uninstall it while upgrading to 2.x, and numpy 2.x would break
# the image's ROS apt packages anyway (built against the numpy 1.26 ABI; see
# the rerun note in scene-viewer.txt). With the cap, the installed 1.26.4
# satisfies scipy and pip skips numpy entirely. Do NOT blanket
# --ignore-installed: the later layers rely on the torch version installed
# here, and ignoring it would re-resolve torch from PyPI.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    without-proxy pip install -r /tmp/requirements/scene-base.txt \
        "numpy<2" \
        --progress-bar on \
        --timeout 60 \
        --retries 3 \
    && rm /tmp/requirements/scene-base.txt

# core
COPY requirements/scene-perception-core.txt /tmp/requirements/scene-perception-core.txt
# "numpy<2" here too: keeps the resolver away from opencv versions that
# require numpy>=2 (same ABI argument as the base layer).
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    without-proxy pip install -r /tmp/requirements/scene-perception-core.txt \
        "numpy<2" \
        --progress-bar on \
        --timeout 60 \
        --retries 3 \
    && rm /tmp/requirements/scene-perception-core.txt

# network heavy
COPY requirements/scene-perception-heavy.txt /tmp/requirements/scene-perception-heavy.txt
# "numpy<2": same ABI argument as base/core. --ignore-installed psutil:
# open3d's dash/matplotlib dep tree upgrades psutil, but apt-side psutil
# (pulled in by ros2cli) is Debian-owned with no RECORD — pip cannot
# uninstall it. The pip psutil lands in /usr/local and shadows it.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    without-proxy pip install -r /tmp/requirements/scene-perception-heavy.txt \
        "numpy<2" \
        --ignore-installed psutil \
        --progress-bar on \
        --timeout 60 \
        --retries 3 \
    && rm /tmp/requirements/scene-perception-heavy.txt

# Keep this runtime in the major line the deployment's stubs are generated in.
# Scene imports stubs produced by the same host codegen as the Webots packages,
# and those are pinned to protobuf 6.33.6 by
# examples/webots/scripts/run_python_codegen.sh; a runtime in a different major
# rejects them at import ("gencode 7.35.1 runtime 6.33.6"). The floor is here
# because the base ROS image ships something older still.
RUN without-proxy pip install --upgrade "protobuf==6.33.6"

# Restore the setuptools pin scene-base deliberately sets (69.5.1): open3d's
# dash/matplotlib dep tree upgrades setuptools past what colcon-core accepts
# (<80), and this image runs colcon for its ROS 2 IDL overlay at runtime
# (scripts/build.sh's ros2_idl step). Heavy layer runs above; restore below it.
RUN without-proxy pip install --no-cache-dir "setuptools==69.5.1"

# pytorch3d (see requirements/scene-pytorch3d.txt to decide whether installing it or not.)
# COPY requirements/scene-pytorch3d.txt /tmp/requirements/scene-pytorch3d.txt
# RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
#     without-proxy pip install -r /tmp/requirements/scene-pytorch3d.txt \
#         --progress-bar on \
#         --timeout 60 \
#         --retries 3 \
#     && rm /tmp/requirements/scene-pytorch3d.txt

# ── Proxy-needed network layers start here ─────────────────────────
# Declare build args as late as possible to avoid invalidating earlier
# apt/pip layers when proxy values change.
ARG HTTP_PROXY_HOST
ARG HTTPS_PROXY_HOST
ARG NO_PROXY_HOST
# GitHub mirror prefix (RBNX_GH_MIRROR in scripts/build.sh); empty clones
# from github.com directly.
ARG GITHUB_PREFIX=https://ghfast.top/

# concept-graphs source from the ali-dev branch.
# git clone: use proxy.
RUN set -eux; \
    rm -rf /opt/concept-graphs; \
    with-build-proxy git clone --depth 1 --branch ali-dev \
        ${GITHUB_PREFIX}https://github.com/concept-graphs/concept-graphs.git \
        /opt/concept-graphs \
    || ( \
        rm -rf /opt/concept-graphs && \
        with-build-proxy git clone --depth 1 --branch ali-dev \
            https://github.com/concept-graphs/concept-graphs.git \
            /opt/concept-graphs \
    )

# concept-graphs editable install.
# pip: do NOT use proxy.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    without-proxy pip install --no-deps -e /opt/concept-graphs

# Bake CV model weights into the image.
ENV HF_HOME=/opt/models/hf \
    YOLO_CONFIG_DIR=/opt/ultralytics

RUN mkdir -p /opt/models /opt/models/hf /opt/models/ultralytics /opt/ultralytics

COPY _weights/yolov8l-world.pt /opt/models/yolov8l-world.pt
COPY _weights/mobile_sam.pt    /opt/models/mobile_sam.pt
COPY _weights/open_clip_pytorch_model.bin /opt/models/open_clip_pytorch_model.bin

# Two CLIP-flavored downloads bake in here:
#   1. open_clip's ViT-B-32 LAION-2B — copied above from the host model cache.
#   2. Ultralytics YOLO-World's text encoder — goes to the Ultralytics
#      weights_dir under /opt/models/ultralytics.
#
# open_clip receives a local checkpoint path, so it never calls the Hugging
# Face metadata API. Ultralytics uses openai/clip internally from
# YOLOWorld.set_classes(); run that exact path at build time so start never
# downloads the 354 MB ViT-B-32.pt into /scene/weights/clip.
RUN with-build-proxy sh <<'EOF'
set -eux
export YOLO_CONFIG_DIR=/opt/ultralytics

python3 -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='/opt/models/open_clip_pytorch_model.bin')"

python3 - <<'PY'
from ultralytics.utils import SETTINGS

SETTINGS.update({
    "weights_dir": "/opt/models/ultralytics",
    "datasets_dir": "/tmp/ultralytics/datasets",
    "runs_dir": "/tmp/ultralytics/runs",
    "sync": False,
})
PY

python3 - <<'PY'
from pathlib import Path
from ultralytics.utils import WEIGHTS_DIR

expected = Path("/opt/models/ultralytics")
if Path(WEIGHTS_DIR) != expected:
    raise RuntimeError(f"Ultralytics WEIGHTS_DIR={WEIGHTS_DIR!s}, expected {expected!s}")

from ultralytics import YOLO

classes = [
    "chair", "table", "desk", "couch", "sofa", "bookshelf", "shelf",
    "cabinet", "drawer", "whiteboard",
    "monitor", "laptop", "keyboard", "mouse", "computer tower",
    "monitor stand", "headphones", "webcam", "router", "power strip",
    "cup", "mug", "water bottle", "thermos", "paper cup",
    "backpack", "handbag", "book", "notebook", "pen", "pencil",
    "phone", "tablet",
    "box", "cardboard box", "tray", "basket", "trash bin",
    "tool", "screwdriver", "wrench", "tape",
    "plant", "potted plant", "lamp", "clock", "picture frame",
    "snack", "fruit", "apple", "banana",
    "door", "doorway", "fire extinguisher", "person",
]

model = YOLO("/opt/models/yolov8l-world.pt")
model.set_classes(classes)
PY

test -s /opt/models/ultralytics/clip/ViT-B-32.pt
chmod -R a+rX,u+rwX /opt/ultralytics /opt/models/ultralytics

ls -la /opt/models/ /opt/models/ultralytics/clip/
EOF

# No global proxy ENV was set, so there is no build-time proxy to clear here.

# Fixed env so perception_concept_graphs.py knows where the weights
# live without each deployment having to override.
ENV SCENE_YOLO_WORLD_WEIGHTS=/opt/models/yolov8l-world.pt \
    SCENE_MOBILE_SAM_WEIGHTS=/opt/models/mobile_sam.pt \
    YOLO_CONFIG_DIR=/opt/ultralytics \
    SCENE_CLIP_MODEL=ViT-B-32 \
    SCENE_CLIP_PRETRAINED=/opt/models/open_clip_pytorch_model.bin

# viewer (see the file for why this one is --no-deps). Last, so bumping it
# reuses every heavy layer above.
COPY requirements/scene-viewer.txt /tmp/requirements/scene-viewer.txt
# The browser half of the viewer is the npm package of the same version: the
# page and the recording are one protocol. It lives in the image rather than
# the source tree so a fresh clone has it after `rbnx build`, with nothing to
# fetch by hand; scene serves it from RERUN_VIEWER_DIR (rerun_sink.py).
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    without-proxy pip install --no-deps -r /tmp/requirements/scene-viewer.txt \
        --progress-bar on --timeout 60 --retries 3 \
    && v="$(sed -n "s/^rerun-sdk==//p" /tmp/requirements/scene-viewer.txt)" \
    && mkdir -p /opt/rerun-web-viewer \
    && curl -fSL --retry 5 --retry-delay 2 \
        "${NPM_REGISTRY}/@rerun-io/web-viewer/-/web-viewer-${v}.tgz" \
        | tar xz -C /opt/rerun-web-viewer --strip-components=1 \
            package/index.js package/re_viewer.js package/re_viewer_bg.wasm \
    && rm /tmp/requirements/scene-viewer.txt

WORKDIR /scene

COPY entrypoint.sh /entrypoint.sh
COPY no_shm_profile.xml /etc/fastrtps_no_shm.xml

RUN chmod +x /entrypoint.sh

# Left for operators who explicitly override RMW back to FastRTPS.
ENV FASTRTPS_DEFAULT_PROFILES_FILE=/etc/fastrtps_no_shm.xml

ENV RMW_IMPLEMENTATION=rmw_zenoh_cpp

ENTRYPOINT ["/entrypoint.sh"]
