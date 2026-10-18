# Remote Docker through SSH

The toolchain installer installs Debian's `docker-cli`, Compose v2 and Buildx.
No local Docker daemon is installed or advertised. Use **Linux: Configure Remote
Docker over SSH** with an endpoint such as `ssh://developer@build-host:22` and a
new context name. Passwords in URLs, TCP daemons, paths and option-like names are
rejected. Existing contexts are not overwritten.

The remote machine must already have Docker Engine and SSH, and your remote user
must have Docker access. Configure your own SSH key inside Linux `/root/.ssh`;
the setup does not read, copy or generate private credentials on your behalf.
Verify the host fingerprint through the interactive SSH verification terminal.
Strict host-key checking is not disabled. SSH's ordinary config and key-agent
facilities remain available.

The extension remembers only the endpoint and context name. Check Connection
runs a bounded `docker --context NAME info` and a local Compose version check.
A successful context creation is not reported as a successful daemon connection.

```sh
docker --context tablet-remote ps
docker --context tablet-remote build -t myapp .
docker --context tablet-remote compose up -d
docker --context tablet-remote logs --follow my-container
docker context use tablet-remote
```

Build contexts are uploaded from the tablet. Bind mounts refer to paths on the
remote Docker host, not `/workspace` on the tablet. For bind-mounted development,
clone/sync the project onto that host or use remote volumes. The fork does not
publish a Docker socket or an unauthenticated network daemon.

During this build, the user authorized the CachyOS test host and provisioning a
dedicated tablet key. Its private key remains in Linux home; its public key was
added with OpenSSH `restrict` options (no PTY, agent, X11 or port forwarding).
The known host key was copied through the Mac's already-verified SSH connection.
See the implementation report for the actual Docker test results.

Android/Linux may not resolve `.local` names through public DNS. For the test
host, Linux `~/.ssh/config` maps the mDNS alias to its verified LAN address. Update
that mapping if DHCP changes the host address. Do not disable host-key checking.
To revoke the dedicated test key, remove the public-key entry whose comment is
`vscodroid-linux-tablet-20261018` from the remote account's `authorized_keys`.
