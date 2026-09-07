# -*- coding: utf-8 -*-
"""确认压测配置（不打印密钥）"""
for ln in open('.env', encoding='utf-8').read().splitlines():
    if ln and not ln.startswith('#') and not ln.startswith('LLM_API_KEY'):
        print(ln)
