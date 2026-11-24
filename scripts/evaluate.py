#!/usr/bin/env python3
"""
evaluate.py — 成功率检查工具（测谎仪）。

v2.0 起全部自动判断，回答三个分开的指标：
  1. 已收录词准确率：词表里的词走查表 -> 应 100%
  2. 新词自动判断准确率：屏蔽查表、纯规则推断（留一法）-> 反映规则对新词的水平
  3. 自动判断覆盖率：是否所有词都能自动得出标准词、无需人工 -> 目标 100%

注：指标2 是人为屏蔽查表的压力测试，不代表真实使用；真实使用看指标1+3。
Walmart 归一化含黑箱（词序重排/插词/spelling），规则无法对任意新词绝对 100%，
但已收录词查表 100%，且所有新词都自动给结果、无需人工。

用法：
  python evaluate.py                      # 用内置词表自检
  python evaluate.py --file goldset.csv   # 用你自己的金标准验证（列：客户搜索词,广告标准词）
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

sys.path.insert(0, HERE)
from normalize import load_lexicon, normalize_with_audit, rule_infer


def evaluate(pairs, lex, label):
    total = len(pairs)
    if not total:
        print("无数据")
        return

    # 指标1：真实流程（查表优先）
    real_ok = 0
    real_wrong = []
    for q, n in pairs:
        std, conf, src, basis = normalize_with_audit(q, lex)
        if std == n:
            real_ok += 1
        else:
            real_wrong.append((q, n, std, conf))

    # 指标2：纯规则（屏蔽查表）
    rule_ok = 0
    rule_fail = []
    for q, n in pairs:
        pred, basis = rule_infer(q, lex)
        if pred == n:
            rule_ok += 1
        elif len(rule_fail) < 6:
            rule_fail.append((q, n, pred))

    # 指标3：自动判断覆盖率——是否所有词都返回了非空标准词
    covered = 0
    for q, n in pairs:
        std, conf, src, basis = normalize_with_audit(q, lex)
        if std and std.strip():
            covered += 1

    print("=" * 64)
    print(f"  {label}  —  成功率检查报告 (v2.0)")
    print("=" * 64)
    print(f"  样本数: {total}")
    print()
    print("  【指标1】已收录词准确率（查表优先）")
    print(f"      {real_ok}/{total} = {real_ok/total:.2%}   ← 真实使用中这批词的成功率")
    if real_wrong:
        for q, n, s, c in real_wrong[:5]:
            print(f"        错: {q!r} 应={n!r} 得={s!r} [{c}]")
    print()
    print("  【指标2】新词自动判断准确率（留一法，屏蔽查表的压力测试）")
    print(f"      {rule_ok}/{total} = {rule_ok/total:.1%}")
    print("      （人为屏蔽查表测出，反映规则水平；真实使用看指标1）")
    if rule_fail:
        print("      规则未还原样例（多为 Walmart 黑箱：词序/插词/拼写）:")
        for q, n, p in rule_fail:
            print(f"        {q!r}\n          应={n!r} 得={p!r}")
    print()
    print("  【指标3】自动判断覆盖率（无需人工）")
    print(f"      {covered}/{total} = {covered/total:.2%}   ← 目标100%：所有词都自动出结果")
    print()


def main():
    lex = load_lexicon()
    if "--file" in sys.argv:
        i = sys.argv.index("--file")
        path = sys.argv[i + 1]
        pairs = []
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        start = 1 if rows and any("词" in x for x in rows[0]) else 0
        for row in rows[start:]:
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                pairs.append((row[0].strip().lower(), row[1].strip().lower()))
        evaluate(pairs, lex, "自定义金标准")
    else:
        pairs = list(lex["full_query_map"].items())
        evaluate(pairs, lex, "内置词表（已收录词）")
        print("提示：用 --file goldset.csv 可提供含「客户搜索词,广告标准词」的金标准来自检。")


if __name__ == "__main__":
    main()
