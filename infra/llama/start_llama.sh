#!/usr/bin/env bash

LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"

$LLAMA_SERVER \
  -m /mnt/c/models/llama3-8b-instruct-q5_k_m.gguf \
  --port 8000 \
  --ctx-size 8192
