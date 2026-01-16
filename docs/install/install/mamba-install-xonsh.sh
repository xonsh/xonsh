#!/bin/sh

set -eu

echo
echo Install xonsh using micromamba
echo

TARGET_DIR="${TARGET_DIR:-${HOME}/.local/xonsh-env}"
PYTHON_VER="${PYTHON_VER:-3.11}"
XONSH_VER="${XONSH_VER:-xonsh[full]}"
PIP_INSTALL="${PIP_INSTALL:-}"
XONSHRC="${XONSHRC:-}"


MAMBA_BIN_DIR="${TARGET_DIR}/bin"
MAMBA_USE_CONDA_FORGE="${MAMBA_USE_CONDA_FORGE:-yes}"

echo
echo Env
echo
echo TARGET_DIR=$TARGET_DIR
echo PYTHON_VER=$PYTHON_VER
echo MAMBA_USE_CONDA_FORGE=$MAMBA_USE_CONDA_FORGE

echo
echo Create directories
echo

mkdir -p $TARGET_DIR $MAMBA_BIN_DIR $TARGET_DIR/xbin
cd $TARGET_DIR


echo
echo Install micromamba
echo

# START INSTALLING MAMBA -- Code from https://github.com/mamba-org/micromamba-releases/blob/main/install.sh

# Computing artifact location
case "$(uname)" in
  Linux)
    PLATFORM="linux" ;;
  Darwin)
    PLATFORM="osx" ;;
  *NT*)
    PLATFORM="win" ;;
esac

ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|ppc64le|arm64)
      ;;  # pass
  *)
    ARCH="64" ;;
esac

case "$PLATFORM-$ARCH" in
  linux-aarch64|linux-ppc64le|linux-64|osx-arm64|osx-64|win-64)
      ;;  # pass
  *)
    echo "Failed to detect your OS" >&2
    exit 1
    ;;
esac

if [ "${VERSION:-}" = "" ]; then
  RELEASE_URL="https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-${PLATFORM}-${ARCH}"
else
  RELEASE_URL="https://github.com/mamba-org/micromamba-releases/releases/download/micromamba-${VERSION}/micromamba-${PLATFORM}-${ARCH}"
fi


# Downloading artifact
mkdir -p "${MAMBA_BIN_DIR}"
if hash curl >/dev/null 2>&1; then
  curl "${RELEASE_URL}" -o "${MAMBA_BIN_DIR}/micromamba" -fsSL --compressed ${CURL_OPTS:-}
elif hash wget >/dev/null 2>&1; then
  wget ${WGET_OPTS:-} -qO "${MAMBA_BIN_DIR}/micromamba" "${RELEASE_URL}"
else
  echo "Neither curl nor wget was found" >&2
  exit 1
fi
chmod +x "${MAMBA_BIN_DIR}/micromamba"


# Initializing conda-forge
case "$MAMBA_USE_CONDA_FORGE" in
  y|Y|yes)
    "${MAMBA_BIN_DIR}/micromamba" config append channels conda-forge
    "${MAMBA_BIN_DIR}/micromamba" config append channels nodefaults
    "${MAMBA_BIN_DIR}/micromamba" config set channel_priority strict
    ;;
esac

# FINISH INSTALLING MAMBA

echo
echo Install xonsh
echo

cat > ./xbin/xmamba.xsh <<EOF
if \$XONSH_MODE != 'source':
    printx('Run: source xmamba.xsh', 'YELLOW')
    exit(1)
\$MAMBA_ROOT_PREFIX = \$(which xonsh)[:-10]
execx(\$(@(\$MAMBA_ROOT_PREFIX+'/bin/micromamba') shell hook --shell xonsh).replace("aliases['micromamba']", "aliases['xmamba']"))
EOF
chmod +x ./xbin/xmamba.xsh

cat > ./xbin/xbin-add <<EOF
#!/bin/bash
ln -s $MAMBA_BIN_DIR/"\$@" $MAMBA_BIN_DIR/../xbin/"\$@"
ls $MAMBA_BIN_DIR/../xbin/"\$@"
EOF
chmod +x ./xbin/xbin-add

cat > ./xbin/xbin-del <<EOF
#!/bin/bash
rm -i $MAMBA_BIN_DIR/../xbin/"\$@"
EOF
chmod +x ./xbin/xbin-del

cat > ./xbin/xbin-list <<EOF
#!/bin/bash
ls -1 $MAMBA_BIN_DIR/../xbin/ | grep -v xbin-
EOF
chmod +x ./xbin/xbin-list

cat > ./xbin/xbin-hidden <<EOF
#!/bin/bash
ls -1 $MAMBA_BIN_DIR/
EOF
chmod +x ./xbin/xbin-hidden

export MAMBA_ROOT_PREFIX="$TARGET_DIR"
eval "$($MAMBA_BIN_DIR/micromamba shell hook --shell bash)"
micromamba activate base
micromamba install -y python=$PYTHON_VER

echo
echo Install $XONSH_VER
echo
"$TARGET_DIR/bin/python" -m pip install $XONSH_VER

if [ -n "$PIP_INSTALL" ]; then
    echo
    echo Install: $PIP_INSTALL
    echo
    "$TARGET_DIR/bin/python" -m pip install $(echo $PIP_INSTALL)
fi

ln -s $TARGET_DIR/bin/xonsh ./xbin/xonsh
ln -s xonsh ./xbin/xbin-xonsh  # to run xonsh from xonsh env if xonsh overwritten by $PATH
ln -s ../bin/python ./xbin/xbin-python  # to run python from xonsh env


if [ -n "$XONSHRC" ]; then
    echo
    echo Update ~/.xonshrc
    echo
    echo $XONSHRC >> ~/.xonshrc
fi

echo
echo 'Test xonsh'
echo
${TARGET_DIR}/xbin/xonsh --no-rc --no-env -c "echo @(21+21)"

echo
echo 'Result'
echo
echo "TARGET_DIR=$TARGET_DIR"
echo "PYTHON_VER=$PYTHON_VER"
echo "MAMBA_USE_CONDA_FORGE=$MAMBA_USE_CONDA_FORGE"
echo
echo 'Now you can:'
echo
echo '  * Add `xbin` dir to the top of your system shell path:'
echo
echo "      echo 'export PATH=${TARGET_DIR}/xbin:\$PATH' >> ~/.zshrc"
echo "      echo 'export PATH=${TARGET_DIR}/xbin:\$PATH' >> ~/.bashrc"
echo '      # Restart session and run xonsh.'
echo
echo "  * Or run xonsh manually by path from any place:"
echo
echo "      ${TARGET_DIR}/xbin/xonsh"
echo