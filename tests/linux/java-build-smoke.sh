#!/bin/bash
set -eu
base=$(mktemp -d /workspace/java-build-smoke.XXXXXXXX)
cd "$base"
mkdir -p src/main/java
cat > src/main/java/Hello.java <<'JAVA'
public class Hello { public static void main(String[] args) { System.out.println("JAVA_BUILD_OK 42"); } }
JAVA
cat > pom.xml <<'POM'
<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>local.vscodroid</groupId><artifactId>smoke</artifactId><version>1.0</version><properties><maven.compiler.source>17</maven.compiler.source><maven.compiler.target>17</maven.compiler.target></properties></project>
POM
timeout 600 mvn -B -q package
java -cp target/classes Hello
cat > build.gradle <<'GRADLE'
apply plugin: 'java'
sourceCompatibility = 1.8
targetCompatibility = 1.8
GRADLE
timeout 600 gradle --no-daemon --console plain build
java -cp build/classes/java/main Hello
printf 'JAVA_BUILD_TOOLS_OK %s\n' "$base"
