cd ..
pip install -e .
cd verl
pip install -e .
pip install torch==2.6.0
pip install vllm==0.8.5
pip install flash_attn==2.7.4.post1
pip install flashinfer-python==0.2.2.post1 # forgot this -> outside the if statement
pip install -U ray==2.46.0

