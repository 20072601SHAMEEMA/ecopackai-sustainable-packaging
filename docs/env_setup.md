# Environment Setup Guide — EcoPackAI

Two ways to run this project: a local conda environment for day-to-day development, or Docker for a fully containerized, reproducible setup. You don't need both — conda is faster for daily coding, Docker matters when you want the whole stack (backend + database + pgAdmin) running together.

## Option 1: Conda Environment (local development)

Anaconda is already installed, so no extra tools needed.

```bash
# Create the environment
conda create -n ecopackai python=3.11 -y

# Activate it
conda activate ecopackai

# Install dependencies
pip install -r environments/requirements.txt
```

Register the environment as a Jupyter kernel (one time only), so notebooks run with the
same library versions as the scripts, the API and Docker:

```bash
python -m ipykernel install --user --name ecopackai-conda --display-name "Python (EcoPackAI conda)"
```

In Jupyter, open a notebook and choose **Kernel → Change kernel → Python (EcoPackAI conda)**.
All notebooks in `ml/notebooks/` are already set to this kernel.

**Why this matters:** models and pipelines are saved with `joblib` (pickle). A pickle saved
with one scikit-learn version may not load correctly with another. Everything in this project
(notebooks, `ml/training/`, the Flask API, Docker) must use the same scikit-learn version
pinned in `requirements.txt` (1.5.1).

To add a new dependency, install it in this env and add it to `environments/requirements.txt`
with its exact version (`pip show <package>` prints it). Avoid `pip freeze >`, which also dumps
every sub-dependency and local path and makes the file hard to install on other machines.

To deactivate when done:

```bash
conda deactivate
```

## Option 2: Docker (full containerized stack)

Requires Docker Desktop installed and running.

From the `environments/` folder:

```bash
# Build and start all containers (backend, PostgreSQL, pgAdmin)
docker-compose up --build

# Stop all containers
docker-compose down
```

This starts three services:

| Service | Purpose | Access |
|---|---|---|
| backend | Flask API | http://localhost:5000 |
| db | PostgreSQL database | localhost:5432 |
| pgadmin | Database GUI | http://localhost:5050 |

**pgAdmin login:** `admin@ecopackai.com` / `admin` (change these in `docker-compose.yml` before sharing this repo publicly).

**Database connection inside pgAdmin:** host `db`, port `5432`, user `ecopack_user`, password `ecopack_pass`, database `ecopackai_db`.

The database schema (`backend/db/schema.sql`) is loaded automatically the first time the `db` container starts.

## Notes

- Use conda while writing and testing ML/feature-engineering code day to day — faster feedback loop.
- Use Docker when testing the full system end to end, or before handing the project off / deploying, to confirm everything works outside your personal machine setup.
- Never commit real database credentials — the ones in `docker-compose.yml` here are local development placeholders only.