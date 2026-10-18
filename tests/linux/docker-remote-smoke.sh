#!/bin/bash
# Requires explicit permission to use this host and create temporary resources.
# Runs inside Debian. SSH credentials must already be configured in Linux home.
set -euo pipefail
endpoint=${1:?Usage: docker-remote-smoke.sh ssh://user@host:port}
case "$endpoint" in ssh://*) ;; *) echo 'SSH endpoint required' >&2; exit 2;; esac
work=$(mktemp -d /workspace/docker-smoke.XXXXXXXX)
cd "$work"
project="vscodroid-smoke-$(basename "$work" | tr '[:upper:].' '[:lower:]-')"
image="$project:verification"
export DOCKER_CONFIG="$work/docker-config"
export DOCKER_CONTEXT=vscodroid-test
docker context create "$DOCKER_CONTEXT" --docker "host=$endpoint"
base_existed=false
if docker image inspect alpine:3.21 >/dev/null 2>&1; then base_existed=true; fi
cleanup() {
    docker compose -p "$project" down --remove-orphans >/dev/null 2>&1 || true
    docker image rm "$image" >/dev/null 2>&1 || true
    if [ "$base_existed" = false ]; then docker image rm alpine:3.21 >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}'
docker info --format 'Remote={{.OSType}}/{{.Architecture}}'
printf 'REMOTE_BUILD_CONTEXT_OK 世界\n' > message.txt
cat > Dockerfile <<'EOF'
FROM alpine:3.21
COPY --chmod=0444 message.txt /message.txt
USER 65534:65534
CMD ["cat", "/message.txt"]
EOF
docker build --network=none -t "$image" .
cat > compose.yaml <<EOF
services:
  demo:
    image: $image
    network_mode: none
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
EOF
docker compose -p "$project" up --abort-on-container-exit --exit-code-from demo
docker compose -p "$project" logs --no-color demo | tee container.log
grep -q 'REMOTE_BUILD_CONTEXT_OK 世界' container.log
cleanup
trap - EXIT
test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
if docker image inspect "$image" >/dev/null 2>&1; then echo 'Test image cleanup failed' >&2; exit 1; fi
printf 'REMOTE_DOCKER_SMOKE_OK project=%s\n' "$project"
