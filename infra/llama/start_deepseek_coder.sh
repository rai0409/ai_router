#!/usr/bin/env bash

LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"

$LLAMA_SERVER \
  -m /mnt/c/models/deepseek-coder-v2-lite-q5_k_m.gguf \
  --port 8001 \
  --ctx-size 8192
