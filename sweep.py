# -*- coding: utf-8 -*-
"""并发梯度扫测：5/10/20/30/40/50 各 60 秒，输出 RPS 与百分位对照表"""
import subprocess
import sys

PY = r"D:\Software\anaconda\anaconda_envs\Factory_env\python.exe"
LEVELS = [5, 10, 20, 30, 40, 50]

for users in LEVELS:
    print("\n" + "#" * 20 + " 并发 %d " % users + "#" * 20, flush=True)
    subprocess.run([PY, "loadgen.py", str(users), "60"])
