# run_local_llama.ps1
# ローカル Llama サーバー起動スクリプト

$llamaExe  = "C:\Users\raira\projects\llama.cpp\build\bin\llama-server.exe"
$modelPath = "C:\models\llama3-8b-instruct-q5_k_m.gguf"

& $llamaExe `
  -m $modelPath `
  --host 127.0.0.1 `
  --port 8000
