# Docker guide

The repository includes a `Containerfile`. The image runs TickTask in a container.

## Build the image

Run this command from the repository root:

```bash
docker build -f Containerfile -t ticktask .
```

If you use Podman, replace `docker` with `podman`.

## Run the container

Run the container in an interactive terminal:

```bash
docker run --rm -it ticktask
```

The image sets the default command to `ticktask --no-tray`.

## Persist the database

The container stores data under `/data`. The image sets `XDG_DATA_HOME=/data` and declares `/data` as a volume.

Mount a host directory to keep the database after the container stops:

```bash
docker run --rm -it -v ticktask-data:/data ticktask
```

This command uses the named volume `ticktask-data`.

## Run timer-only mode

Pass the timer-only option after the image name:

```bash
docker run --rm -it ticktask --pomodoro-only
```

## Notes

- The container runs as the `ticktask` user.
- The image installs dependencies from `uv.lock` with `uv sync --frozen --no-dev`.
- Use an interactive terminal for the Textual interface.
