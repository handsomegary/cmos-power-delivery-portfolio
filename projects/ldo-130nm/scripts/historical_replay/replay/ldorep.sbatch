#!/usr/bin/env bash
#SBATCH --job-name=ldo-psf-replay3220
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --no-requeue
#SBATCH --output=slurm-ldorep-%j.log
set -eo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
sha256sum --quiet -c SHA256SUMS
unset OA_HOME LD_LIBRARY_PATH PYTHONOPTIMIZE
export PYTHONDONTWRITEBYTECODE=1 LC_ALL=C
source "${CADENCE_SETUP:?set CADENCE_SETUP to the site IC setup script}"
export PATH="${SPECTRE_BIN:?set SPECTRE_BIN}:$PATH"
LDO_WORKERS=2 LDO_WALL_S=19800 python3 ldorep.py
