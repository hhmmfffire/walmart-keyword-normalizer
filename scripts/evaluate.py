#!/usr/bin/env python3
"""
evaluate.py — 成功率检查工具（测谎仪）。

回答三个不同的"成功率"，绝不混为一谈：
  1. 已收录词准确率：词表里的词走真实流程（查表优先）→ 应该 100%
  2. 新词规则准确率：屏蔽查表、纯规则推断（留一法）→ 反映规则本身水平
  3. 结果可靠性：判错时是否被「需确认」拦截（拦截=不会混进投放）→ 目标 100%

用法：
  python evaluate.py                      # 用内置词表自检
  python evaluate.py --file goldset.csv   # 用你自己的金标准验证（列：客户搜索词,广告标准词）
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
LEXICON_PATH = os.path.join(SKILL_DIR, "data", "lexicon.json")

sys.path.insert(0, HERE)
from normalize import load_lexicon, normalize_with_audit, rule_infer, CONF_REVIEW, CONF_SAMPLE, CONF_HIGH


def evaluate(pairs, lex, label):
    total = len(pairs)
    if not total:
        print("无数据")
        return

    # 指标1：真实流程（查表优先）
    real_ok = 0
    real_wrong = []
    for q, n in pairs:
        std, conf, src, doubts = normalize_with_audit(q, lex)
        if std == n:
            real_ok += 1
        else:
            real_wrong.append((q, n, std, conf))

    # 指标2+3：纯规则（屏蔽查表）
    rule_ok = 0
    caught = 0       # 判错但被拦截
    silent = 0       # 判错且没拦截
    silent_ex = []
    for q, n in pairs:
        pred, doubts = rule_infer(q, lex)
        if pred == n:
            rule_ok += 1
        else:
            if doubts:
                caught += 1
            else:
                silent += 1
                if len(silent_ex) < 8:
                    silent_ex.append((q, n, pred))

    print("=" * 64)
    print(f"  {label}  —  成功率检查报告")
    print("=" * 64)
    print(f"  样本数: {total}")
    print()
    print("  【指标1】真实使用准确率（查表优先）")
    print(f"      {real_ok}/{total} = {real_ok/total:.2%}   ← 你实际得到的成功率")
    if real_wrong:
        for q, n, s, c in real_wrong[:5]:
            print(f"        错: {q!r} 应={n!r} 得={s!r} [{c}]")
    print()
    print("  【指标2】纯规则推断准确率（留一法，衡量规则本身）")
    print(f"      {rule_ok}/{total} = {rule_ok/total:.1%}")
    print()
    print("  【指标3】结果可靠性（错误是否被「需确认」拦截）")
    print(f"      判错总数: {total - rule_ok}")
    print(f"        - 已拦截(安全): {caught}")
    print(f"        - 漏过(危险):   {silent}")
    safety = (total - silent) / total
    print(f"      可靠性 = {safety:.2%}   ← 目标100%：错误绝不混进投放")
    if silent_ex:
        print("      漏过样例:")
        for q, n, p in silent_ex:
            print(f"        {q!r}\n          应={n!r} 得={p!r}")
    print()


def main():
    lex = load_lexicon()
    if "--file" in sys.argv:
        i = sys.argv.index("--file")
        path = sys.argv[i + 1]
        pairs = []
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
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
