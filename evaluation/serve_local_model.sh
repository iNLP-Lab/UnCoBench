#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:?Usage: bash evaluation/serve_local_model.sh MODEL_PATH MODEL_NAME [vLLM options...]}"
MODEL_NAME="${2:?Specify the model name to expose in the API}"
shift 2

exec vllm serve "$MODEL_PATH" \
  --served-model-name "$MODEL_NAME" \
  --host 127.0.0.1 \
  --port "${VLLM_PORT:-8000}" \
  --tensor-parallel-size "${VLLM_TP_SIZE:-1}" \
  "$@"
