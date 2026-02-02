This is a one-liner for development using docker (to access linux platform).

`docker run -ti -v g36cache:/root/.openmodelica,/root/.cache -v ../:/work -w /work  --rm ghcr.io/prefix-dev/pixi:latest pixi shell -e simulation`

* `docker` or `podman`
* `ti` interactive terminal
* `g36cache` is a named volume to persist openmodelica and pixi downloads
* `-v ../:/work` mounts local files. doubles as a way to persist project python and conda packages because those are in [.pixi](../.pixi/envs/).
* `-w /work` sets the working directory
* `--rm` removes the container when you're done to reduce clutter
* `-e simulation` sets up the 'simulation' environment as defined in [pyproject.toml](../pyproject.toml).
