from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"
RUNTIME_DIR = PROJECT_ROOT / "runtime"


def ask_yes_no(prompt, default=False):
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        value = input(prompt + suffix).strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please enter y or n.")


def read_env_lines(env_path=ENV_PATH):
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines()


def get_env_value(key, env_path=ENV_PATH):
    prefix = key + "="
    for line in read_env_lines(env_path):
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):]
    return None


def write_env_value(key, value, *, env_path=ENV_PATH, update_direct=False, ask_overwrite=True):
    value = str(value)
    if not update_direct:
        print(f"{key}={value}")
        return False

    lines = read_env_lines(env_path)
    prefix = key + "="
    found_index = None
    old_value = None

    for index, line in enumerate(lines):
        if line.strip().startswith(prefix):
            found_index = index
            old_value = line.strip()[len(prefix):]
            break

    if found_index is not None:
        if ask_overwrite and not ask_yes_no(f"{key} already exists. Overwrite?"):
            print(f"Kept existing {key}.")
            return False
        lines[found_index] = f"{key}={value}"
        action = "Updated"
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")
        action = "Added"

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if old_value is None:
        print(f"{action} {key} in {env_path}.")
    else:
        print(f"{action} {key} in {env_path}.")
    return True


def write_many_env_values(values, *, update_direct=False):
    changed = []
    for key, value in values.items():
        if write_env_value(key, value, update_direct=update_direct):
            changed.append(key)
    return changed


def print_header(title):
    print("\n" + title)
    print("-" * len(title))


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR
