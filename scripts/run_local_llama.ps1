# run_local_llama.ps1
# ローカル Llama サーバー起動スクリプト

$llamaExe  = "C:\Users\raira\projects\llama.cpp\build\bin\llama-server.exe"
$modelPath = "C:\Users\raira\projects\llama.cpp\models\Meta-Llama-3-8B-Instruct-Q5_K_M.gguf"

& $llamaExe `
  -m $modelPath `
  --host 127.0.0.1 `
  --port 8000