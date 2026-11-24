#!/usr/bin/env bash
# replay_hydrophone_stream.sh
# Streams hydrophone audio into MediaMTX over RTSP using FFmpeg.
# Strictly audio-only (zero video tracks) in AAC-LC format per SonaVault spec.

set -euo pipefail

AUDIO_FILE="${1:-/tmp/claude-1000/-home-easemyai-Desktop-shubham-SonaVault/54b453c8-1701-4f9d-ae00-355ccf7726da/scratchpad/test_audio/fleurs_en_sample.wav}"
STATION_CODE="${2:-OC02}"
MEDIAMTX_HOST="${3:-localhost}"
MEDIAMTX_PORT="${4:-8554}"

if [ ! -f "${AUDIO_FILE}" ]; then
    echo "[!] Audio file not found: ${AUDIO_FILE}"
    echo "Usage: $0 [audio_file.wav] [station_code] [mediamtx_host] [mediamtx_port]"
    exit 1
fi

RTSP_TARGET="rtsp://${MEDIAMTX_HOST}:${MEDIAMTX_PORT}/hydrophone/${STATION_CODE}"

echo "=========================================================="
echo " SonaVault Hydrophone RTSP Replay Publisher"
echo " Audio Source : ${AUDIO_FILE}"
echo " Station Code : ${STATION_CODE}"
echo " RTSP Target  : ${RTSP_TARGET}"
echo " Format       : AAC-LC @ 128 kbps, 16/48 kHz (audio-only)"
echo " Pacing       : Real-time (-re), infinite loop (-stream_loop -1)"
echo "=========================================================="

exec ffmpeg -re \
    -stream_loop -1 \
    -i "${AUDIO_FILE}" \
    -vn \
    -c:a aac \
    -b:a 128k \
    -ar 16000 \
    -ac 1 \
    -f rtsp \
    -rtsp_transport tcp \
    "${RTSP_TARGET}"
