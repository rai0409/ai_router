#!/usr/bin/env bash

LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"

$LLAMA_SERVER \
  -m /mnt/c/models/deepseek-r1-distill-llama-8b-q5_k_m.gguf \
  --port 8002 \
  --ctx-size 8192
