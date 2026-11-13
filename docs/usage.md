# Usage and CLI options

## Install and run

1. Install the dependencies:

```bash
uv sync
```

2. Start the application:

```bash
uv run ticktask
```

If you use `pip`, install the project in an active virtual environment with `pip install -e .`. Then run `ticktask`.

## CLI options

Run the command with `uv run ticktask [options]`.

| Option | Action |
| --- | --- |
| `--tray` | Enable the system tray companion. This is the default behavior. |
| `--no-tray` | Disable the system tray companion. |
| `--pomodoro-only` | Start the timer only. This mode does not show project or task screens. |
| `--reset-db` | Delete the local TickTask database after confirmation. Use this option alone. |

## Application modes

- **Full mode:** The application shows project selection, the main timer screen, the task form, and the all-tasks screen.
- **Timer-only mode:** The application shows the Pomodoro screen only.

## Data storage

TickTask stores data in a SQLite database file named `ticktask.db`.

The application places the file in the platform-specific user data directory for the `ticktask` application. The application uses `platformdirs` to select that directory.

The application creates missing parent directories and missing schema objects when the database starts.

## Reset the database

1. Run the reset command:

```bash
uv run ticktask --reset-db
```

2. Read the database path in the prompt.
3. Type `DELETE` to confirm the reset.

The reset command requires an interactive terminal. If you cancel the prompt, the application keeps the database.
If the database file does not exist, the application reports that no database was found.
The reset deletes the database file. The reset does not create a backup.
