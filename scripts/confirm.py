#!/usr/bin/env python3
"""
confirm.py — 把用户确认过的新词回灌词表，让该词永久 100% 可靠。

闭环：normalize.py 标「需确认」的词 -> 你核对后确认真实标准词 -> 本脚本写入 -> 以后查表命中。

用法：
  # 单个确认（客户词 -> 你确认的标准词）
  python confirm.py "客户词" "标准词"

  # 批量确认（CSV，含两列：客户搜索词,广告标准词，已修正好的）
  python confirm.py --file confirmed.csv

确认后自动重新计算统计。样本数据只存本地，不进 GitHub。
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
LEXICON_PATH = os.path.join(SKILL_DIR, "data", "lexicon.json")


def load():
    with open(LEXICON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def save(data):
    with open(LEXICON_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def add_confirmations(data, pairs):
    fq = data.setdefault("full_query_map", {})
    confirmed = data.setdefault("confirmed", {})
    known = set(data.get("known_words", []))
    n = 0
    for raw, std in pairs:
        raw, std = raw.strip().lower(), std.strip().lower()
        if not raw or not std:
            continue
        fq[raw] = std
        confirmed[raw] = {"standard": std, "source": "user-confirmed"}
        # 把标准词的每个词元加入已知
        for w in std.split():
            known.add(w)
        n += 1
    data["known_words"] = sorted(known)
    data["version"] = bump_version(data.get("version", "1.0"))
    save(data)
    return n


def bump_version(v):
    try:
        parts = v.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except Exception:
        return v + ".1"


def main():
    args = sys.argv[1:]
    data = load()
    pairs = []
    if "--file" in args:
        i = args.index("--file")
        with open(args[i + 1], encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        start = 1 if rows and "标准词" in "".join(rows[0]) else 0
        for row in rows[start:]:
            if len(row) >= 2:
                pairs.append((row[0], row[1]))
    elif len(args) >= 2:
        pairs.append((args[0], args[1]))
    else:
        print(__doc__)
        sys.exit(1)

    n = add_confirmations(data, pairs)
    print(f"已确认回灌 {n} 个词，词表现在版本 {data['version']}")
    print(f"总映射: {len(data['full_query_map'])}，确认词: {len(data['confirmed'])}")
    print("这些词以后走查表，100% 可靠。")


if __name__ == "__main__":
    main()
