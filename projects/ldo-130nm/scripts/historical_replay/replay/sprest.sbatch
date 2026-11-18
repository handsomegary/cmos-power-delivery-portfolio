#!/usr/bin/env bash
#SBATCH --job-name=ldo-psf-rest1297
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --no-requeue
#SBATCH --output=slurm-sprest-%j.log
set -eo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
sha256sum --quiet -c SHA256SUMS
unset OA_HOME LD_LIBRARY_PATH PYTHONOPTIMIZE DISPLAY
export PYTHONDONTWRITEBYTECODE=1 LC_ALL=C
source "${CADENCE_SETUP:?set CADENCE_SETUP to the site IC setup script}"
export PATH="${SPECTRE_BIN:?set SPECTRE_BIN}:$PATH"
SP_WORKERS=6 SP_WALL_S=20000 /usr/bin/python3.11 sprest.py
