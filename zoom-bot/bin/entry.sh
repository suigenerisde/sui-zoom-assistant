#!/usr/bin/env bash

# directory for CMake output (matches Dockerfile release preset)
BUILD=build/release

# directory for application output
mkdir -p out

# Set HOME early
export HOME=/root

setup-zoom-cache() {
  # Create ALL cache directories the Zoom SDK might need
  # According to Zoom docs: /home/{username}/.zoomsdk for logs
  mkdir -p /root/.zoomsdk
  mkdir -p /root/.zoomus
  mkdir -p /root/.zoom
  mkdir -p /root/.config/zoomus
  mkdir -p /tmp/.zoomus
  mkdir -p /tmp/zoom

  # Make them all writable
  chmod -R 777 /root/.zoomsdk /root/.zoomus /root/.zoom /root/.config/zoomus /tmp/.zoomus /tmp/zoom 2>/dev/null || true

  # Create zoomus.conf config file
  echo -e "[General]\nsystem.audio.type=default" > /root/.config/zoomus.conf

  echo "Zoom SDK cache directories created"
}

setup-pulseaudio() {
  # Enable dbus
  if [[  ! -d /var/run/dbus ]]; then
    mkdir -p /var/run/dbus
    dbus-uuidgen > /var/lib/dbus/machine-id 2>/dev/null || true
    dbus-daemon --config-file=/usr/share/dbus-1/system.conf --print-address 2>/dev/null || true
  fi

  usermod -G pulse-access,audio root 2>/dev/null || true

  # Cleanup to be "stateless" on startup, otherwise pulseaudio daemon can't start
  rm -rf /var/run/pulse /var/lib/pulse /root/.config/pulse/
  mkdir -p ~/.config/pulse/ && cp -r /etc/pulse/* "$_"

  pulseaudio -D --exit-idle-time=-1 --system --disallow-exit 2>/dev/null || true

  # Create a virtual speaker output
  pactl load-module module-null-sink sink_name=SpeakerOutput 2>/dev/null || true
  pactl set-default-sink SpeakerOutput 2>/dev/null || true
  pactl set-default-source SpeakerOutput.monitor 2>/dev/null || true

  echo "PulseAudio setup complete"
}

build() {
  # Check if binary already exists (built in Dockerfile)
  if [[ -f "$BUILD/zoomsdk" ]]; then
    echo "Binary already built, skipping build step"
    return 0
  fi

  # Configure CMake if this is the first run
  [[ ! -d "$BUILD" ]] && {
    cmake -B "$BUILD" -S . --preset release || exit;
    npm --prefix=client install 2>/dev/null || true
  }

  # Rename the shared library (required for SDK)
  LIB="lib/zoomsdk/libmeetingsdk.so"
  [[ ! -f "${LIB}.1" ]] && cp "$LIB"{,.1}

  # Build the Source Code
  cmake --build "$BUILD"
}

run() {
    echo "=== Setting up Zoom SDK environment ==="

    # Suppress Qt debug messages
    export QT_LOGGING_RULES="*.debug=false;*.warning=false"
    export QT_QPA_PLATFORM=offscreen

    # Setup Zoom cache directories BEFORE running
    setup-zoom-cache

    # Setup PulseAudio
    setup-pulseaudio

    # Build CLI arguments from environment variables
    ARGS=""

    # Required: Zoom SDK credentials from environment
    if [[ -n "$ZOOM_CLIENT_ID" ]]; then
        ARGS="$ARGS --client-id=$ZOOM_CLIENT_ID"
        echo "Client ID: configured"
    else
        echo "WARNING: ZOOM_CLIENT_ID not set!"
    fi

    if [[ -n "$ZOOM_CLIENT_SECRET" ]]; then
        ARGS="$ARGS --client-secret=$ZOOM_CLIENT_SECRET"
        echo "Client Secret: configured"
    else
        echo "WARNING: ZOOM_CLIENT_SECRET not set!"
    fi

    # Optional: Meeting to join
    if [[ -n "$ZOOM_JOIN_URL" ]]; then
        ARGS="$ARGS --join-url=$ZOOM_JOIN_URL"
        echo "Join URL: $ZOOM_JOIN_URL"
    fi

    echo "=== Starting SUI-Assistant Bot ==="
    echo "Working directory: $(pwd)"
    echo "HOME: $HOME"
    echo "Cache dirs exist:"
    ls -la /root/.zoomsdk /root/.zoomus 2>/dev/null || echo "  (creating on first run)"

    # Check if binary exists
    if [[ ! -f "$BUILD/zoomsdk" ]]; then
        echo "ERROR: Binary not found at $BUILD/zoomsdk"
        echo "Contents of build directory:"
        ls -la build/ 2>/dev/null || echo "  build/ does not exist"
        ls -la build/release/ 2>/dev/null || echo "  build/release/ does not exist"
        exit 1
    fi

    # Run with verbose output
    echo "Running: $BUILD/zoomsdk $ARGS"
    exec "./$BUILD/zoomsdk" $ARGS
}

# First, setup cache directories (needed even during build for SDK initialization)
setup-zoom-cache

# Build the application
build

# Only run if ZOOM_JOIN_URL is set, otherwise wait for commands
if [[ -n "$ZOOM_JOIN_URL" ]]; then
    echo "Join URL provided, starting bot..."
    run
else
    echo "No ZOOM_JOIN_URL set. Bot built and ready."
    echo "Waiting for join commands via API..."
    # Keep container running
    tail -f /dev/null
fi

