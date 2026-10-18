#!/bin/bash
# Run inside Debian, leaving test sources/results in a dedicated new directory.
set -euo pipefail
work=$(mktemp -d /workspace/vscodroid-smoke.XXXXXX)
cd "$work"
printf '#include <stdio.h>\nint main(void){puts("C_OK");return 0;}\n' > hello.c
gcc hello.c -o hello-c
./hello-c | grep -x C_OK
clang hello.c -o hello-clang
./hello-clang | grep -x C_OK
printf '#include <iostream>\nint main(){std::cout << "CPP_OK" << std::endl;}\n' > hello.cpp
g++ hello.cpp -o hello-cpp
./hello-cpp | grep -x CPP_OK
cat > CMakeLists.txt <<'EOF'
cmake_minimum_required(VERSION 3.20)
project(TabletSmoke C)
add_executable(hello hello.c)
EOF
cmake -S . -B build
cmake --build build
./build/hello | grep -x C_OK
printf 'public class Hello { public static void main(String[] a) { System.out.println("JAVA_OK"); } }\n' > Hello.java
javac Hello.java
java Hello | grep -x JAVA_OK
python3 -c 'print("PYTHON_OK 世界")'
node -e 'console.log("NODE_OK 世界")'
npm --version
mvn --version
gradle --no-daemon --version
ssh -V
git init -q
git -c user.name='VSCodroid smoke' -c user.email='smoke@localhost' add hello.c
git -c user.name='VSCodroid smoke' -c user.email='smoke@localhost' commit -qm 'Verify tablet Git'
git log -1 --format=%s | grep -x 'Verify tablet Git'
docker --version
docker compose version
docker buildx version
clangd --version
python3 /workspace/.vscodroid-tests/clangd-smoke.py
printf 'value = 42\nprint(value)\n' > debug.py
printf 'p 6 * 7\nc\nq\n' | python3 -m pdb debug.py
export DOCKER_CONFIG="$work/docker-client-test"
docker context create smoke-ssh --docker host=ssh://dev@unavailable.invalid:22
docker context inspect smoke-ssh --format '{{.Endpoints.docker.Host}}' | grep -x 'ssh://dev@unavailable.invalid:22'
printf 'services:\n  demo:\n    image: alpine:3.21\n    command: ["echo", "COMPOSE_OK"]\n' > compose.yaml
docker compose config --quiet
printf 'TOOLCHAIN_SMOKE_OK %s\n' "$work"
