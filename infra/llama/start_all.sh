#!/usr/bin/env bash
bash start_llama.sh &
bash start_deepseek_coder.sh &
bash start_deepseek_r1.sh &
wait
