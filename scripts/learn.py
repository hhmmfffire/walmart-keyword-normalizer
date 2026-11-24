#!/usr/bin/env python3
"""
learn.py — 从 Walmart 关键词样本表格中学习归一化知识。

输入：一个或多个 CSV（含 Raw Query / Normalized Query 列，或中文表头）
输出：data/lexicon.json，包含：
  - full_query_map : 完整客户词 -> 标准词（查表，100%可靠）
  - word_lexicon   : 单词级映射（规则兜底用，高置信度）
  - known_words    : 样本中出现过的标准词元（自检用）
  - volatile_words : 映射不一致词元（Walmart 黑箱，遇新词含此词->需确认）
  - ambiguous      : 词元对应关系详情

样本数据只存本地 data/ 目录，不进入 GitHub 仓库。
"""
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
import difflib

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(SKILL_DIR, "data")
LEXICON_PATH = os.path.join(DATA_DIR, "lexicon.json")

HEADER_MAP = {
    "raw": ["raw query", "原始查询", "客户搜索词"],
    "norm": ["normalized query", "标准化查询", "广告标准词"],
}


def detect_header(fieldnames):
    fl = [f.strip().lower() for f in fieldnames]
    raw = next((fieldnames[fl.index(h)] for h in HEADER_MAP["raw"] if h in fl), None)
    norm = next((fieldnames[fl.index(h)] for h in HEADER_MAP["norm"] if h in fl), None)
    return (raw, norm) if raw and norm else None


def clean_token(s):
    from urllib.parse import unquote
    s = unquote(s.lower()).replace("+", " ")
    s = re.sub(r"[\u2019\u2018]", "'", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return s.split()


def learn(files):
    pairs = set()
    for path in files:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            hdr = detect_header(reader.fieldnames or [])
            if not hdr:
                print(f"  [跳过] 无法识别表头: {path}")
                continue
            raw_k, norm_k = hdr
            for row in reader:
                q = (row.get(raw_k) or "").strip().lower()
                n = (row.get(norm_k) or "").strip().lower()
                if q and n:
                    pairs.add((q, n))

    full_map = {}
    known_words = set()
    # raw_word -> Counter(norm_word)，含"保持不变"的映射，用于检测不一致
    raw2norms = defaultdict(Counter)

    for q, n in pairs:
        full_map[q] = n
        qt, nt = clean_token(q), clean_token(n)
        known_words.update(nt)
        sm = difflib.SequenceMatcher(None, qt, nt)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i1, i2):
                    raw2norms[qt[k]][qt[k]] += 1
            elif tag == "replace":
                for a, b in zip(qt[i1:i2], nt[j1:j2]):
                    raw2norms[a][b] += 1
            elif tag == "delete":
                for k in range(i1, i2):
                    raw2norms[qt[k]]["∅"] += 1
            elif tag == "insert":
                for k in range(j1, j2):
                    raw2norms["∅"][nt[k]] += 1

    # 单词级映射：直接用 difflib 的 replace 段（原验证过 95.8% 的逻辑）
    word_map = defaultdict(Counter)
    for q, n in pairs:
        qt, nt = clean_token(q), clean_token(n)
        sm = difflib.SequenceMatcher(None, qt, nt)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            a = " ".join(qt[i1:i2])
            b = " ".join(nt[j1:j2])
            if tag == "delete":
                b = ""
            elif tag == "insert":
                a = ""
            if a and b and a != b:
                word_map[a][b] += 1
    word_lexicon = {}
    ambiguous = {}
    for w, counter in word_map.items():
        total = sum(counter.values())
        best, best_count = counter.most_common(1)[0]
        if len(counter) > 1 and best_count / total < 0.95:
            ambiguous[w] = list(counter.keys())
        if best_count >= 2 or best_count / total >= 0.7:
            word_lexicon[w] = best

    # 不一致词：raw 词在样本中对应 >1 种结果（含保持不变）
    # 这些词在全新词中无法用规则可靠判断 -> 自检标记需确认
    volatile_words = {}
    for w, counter in raw2norms.items():
        outcomes = {k for k in counter if k != "∅"}
        if len(outcomes) > 1:
            # 主导结果占比 < 98% 才算真正危险（避免 99% 主导的误伤）
            total = sum(counter.values())
            top = counter.most_common(1)[0][1]
            if top / total < 0.98:
                volatile_words[w] = dict(counter)

    # quirk 词：Walmart 做了无法预测操作的词。两类：
    #   (a) 被 INSERT 的词（如 otc -> "otc tool"，凭空多出 tool）
    #   (b) 复数被保留但通用规则会改（如 goods/stays 保持，规则会变 good/stay）
    # 这些词出现在全新词中时，规则不可靠 -> 标记需确认
    insert_words = set()
    retained_plural = set()
    for q, n in pairs:
        qt, nt = clean_token(q), clean_token(n)
        sm = difflib.SequenceMatcher(None, qt, nt)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "insert":
                # 被插入的标准词（如 tool / the），以及它前面的触发词（如 otc）
                inserted = [nt[k] for k in range(j1, j2)]
                for w in inserted:
                    insert_words.add(w)            # 被插入的词本身（tool / the）
                # 触发词：仅取紧邻的前一个词。
                # 注意：绝不能取后一个词——"otc tool blood pressure" 中 blood 是后词，
                # 若记为触发词会污染整个血压计类目（blood 是核心词）。
                if j1 > 0:
                    insert_words.add(nt[j1 - 1])
                # 极少数"句首插入定冠词 the"（the sharper image），
                # 仅当插入词是 the 且位于句首时，才记后一个词为触发词
                if j1 == 0 and "the" in inserted and j2 < len(nt):
                    insert_words.add(nt[j2])
            if tag == "equal":
                # 样本中"保持不变"的复数词（以 s 结尾）
                for k in range(i1, i2):
                    w2 = qt[k]
                    if len(w2) > 3 and w2.endswith("s") and not w2.endswith(("ss", "us", "is")):
                        # 若通用规则会改它，则它是 quirk
                        if w2[:-1] in known_words or w2[:-1] in word_map:
                            retained_plural.add(w2)
    # 把 quirk 词并入 volatile（规则遇到它们一律需确认）
    for w in insert_words | retained_plural:
        if w not in volatile_words:
            volatile_words[w] = {"quirk": "Walmart不可预测操作"}

    # 合并旧数据（确认回灌的自定义映射）
    existing = {}
    if os.path.exists(LEXICON_PATH):
        try:
            with open(LEXICON_PATH, encoding="utf-8") as fh:
                existing = json.load(fh)
        except Exception:
            pass
    existing_known = set(existing.get("known_words", []))
    existing_full = existing.get("full_query_map", {})
    full_map.update(existing_full)            # 回灌的词优先保留
    confirmed = existing.get("confirmed", {})

    result = {
        "version": "1.2",
        "sample_pairs": len(pairs),
        "word_lexicon": dict(sorted(word_lexicon.items())),
        "full_query_map": full_map,
        "known_words": sorted(known_words | existing_known),
        "volatile_words": volatile_words,
        "ambiguous": ambiguous,
        "confirmed": confirmed,  # 用户确认回灌的词 {客户词: 标准词}
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LEXICON_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print(f"已学习 {len(pairs)} 组词对")
    print(f"完整查询映射: {len(full_map)}")
    print(f"词元字典: {len(word_lexicon)}")
    print(f"已知词元: {len(known_words)}")
    print(f"不一致词(危险词): {len(volatile_words)}  <- 新词含此词将标「需确认」")
    print(f"输出: {LEXICON_PATH}")
    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python learn.py <样本文件或目录> [...]")
        print("示例: python learn.py 'D:/WM/KP汇总/BL/*.csv' 'D:/WM/KP汇总/XYJ/*.csv'")
        sys.exit(1)
    files = []
    for arg in args:
        if os.path.isdir(arg):
            files.extend(glob.glob(os.path.join(arg, "*.csv")))
        else:
            files.extend(glob.glob(arg))
    files = sorted(set(files))
    print(f"找到 {len(files)} 个样本文件")
    learn(files)
