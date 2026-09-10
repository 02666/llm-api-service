# -*- coding: utf-8 -*-
"""top_p 对比实验：同一个问题，top_p=0.1（保守）vs top_p=1（放开），各问 2 次看风格差异"""
import httpx

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-API-Key": "dev-key-123", "Content-Type": "application/json"}
QUESTION = "用一个比喻形容秋天"


def ask(top_p, label):
    body = {"messages": [{"role": "user", "content": QUESTION}]}
    if top_p is not None:
        body["top_p"] = top_p
    r = httpx.post(BASE + "/v1/chat/completions", headers=HEADERS, json=body, timeout=90)
    if r.status_code == 200:
        print("[%s] %s" % (label, r.json()["content"][:60]))
    else:
        print("[%s] HTTP %s: %s" % (label, r.status_code, r.text[:80]))


print("---- top_p=0.1（只留概率最高的头部候选，保守）----")
ask(0.1, "第1次")
ask(0.1, "第2次")

print("---- top_p=1（不删任何候选，完整分布）----")
ask(1, "第1次")
ask(1, "第2次")
