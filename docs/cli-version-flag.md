# CLI `--version` flag

OpenSAK supports a `--version` argument when launched from the command line.

---

## Print the current version and exit

```bash
opensak --version
# or
python run.py --version
```

Prints the version string (e.g. `1.11.15`) to stdout and exits immediately.
No Qt window is opened.

---

## Run a specific release

```bash
opensak --version=1.11.15
# or
python run.py --version=1.11.15
```

Checks out git tag `v1.11.15` into a temporary worktree and runs that
version's code in a subprocess. The current working tree is not touched.

If the tag does not exist the app exits with an error.

> **Note:** the version must match an existing git tag exactly (e.g. `1.11.15`,
> not `1.11` or `latest`). Use `git tag -l` to see available releases.

---

## Combining with `--feature`

Both flags can be used together:

```bash
opensak --version=1.11.15 --feature db-combo=true
# or
python run.py --version=1.11.15 --feature db-combo=true
```

`--feature` overrides are forwarded to the subprocess, so they apply to the
versioned run as well.
