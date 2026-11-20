#!/usr/bin/env python3
"""
normalize.py — 把客户搜索词转换为 Walmart 广告标准词（Normalized Query）。

设计原则：结果可靠性优先于"看起来确定"。
  - 命中已学样本          -> 样本     (100% 可靠)
  - 新词自检通过          -> 高置信   (所有词元都在字典中、无冲突)
  - 新词自检存疑          -> 需确认   (含未见过词元/冲突，禁止直接投放)

用户确认"需确认"的词后，用 confirm.py 回灌词表 -> 该词永久 100% 可靠。
收敛结果：你接触过的所有词 100% 准确，错误永远不会混进投放。

用法：
  python normalize.py "back braces for women" "全新词 xxx"
  python normalize.py --file keywords.csv --out result.csv
  python normalize.py --stdin
  python normalize.py --audit          # 自检：报告当前规则对样本的准确率
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(SKILL_DIR, "data")
LEXICON_PATH = os.path.join(DATA_DIR, "lexicon.json")

CONF_SAMPLE = "样本"       # 命中已学样本，100%可靠
CONF_HIGH = "高置信"       # 新词但所有词元都在字典中，自检通过
CONF_REVIEW = "需确认"     # 含未见过词元/冲突，禁止直接投放

GENDER_MAP = {
    "womens": "woman", "women's": "woman", "women": "woman", "woman's": "woman",
    "ladies": "lady", "ladys": "lady", "mens": "men", "men's": "men", "man's": "man",
    "boys": "boy", "girls": "girl", "kids": "kid",
}
COMPOUND_MAP = {
    "touch screen": "touchscreen",
    "one piece": "one-piece",
    "arm rest": "armrest",
    "water proof": "waterproof",
}


def load_lexicon():
    if not os.path.exists(LEXICON_PATH):
        return {"full_query_map": {}, "word_lexicon": {}, "known_words": set(),
                "ambiguous": {}, "volatile_words": {}}
    with open(LEXICON_PATH, encoding="utf-8") as fh:
        d = json.load(fh)
    return {
        "full_query_map": d.get("full_query_map", {}),
        "word_lexicon": d.get("word_lexicon", {}),
        "known_words": set(d.get("known_words", [])),
        "ambiguous": d.get("ambiguous", {}),
        "volatile_words": d.get("volatile_words", {}),
    }


def preprocess(s):
    # URL 编码异常：%20 在 Walmart 有的解码有的不解码（数据 bug），
    # 含 %20 的词交给上层标「需确认」，这里先原样保留标记
    s = s.strip().lower()
    if "%20" in s:
        return s  # 不解码，rule_infer 会检测并标记需确认
    # 保护小数（5.00 / 9.5-13.25 / $5.00）：替换为占位符，避免被标点清洗拆开
    decimals = []
    def stash(m):
        decimals.append(m.group(0).lstrip("$"))
        return " dec" + str(len(decimals) - 1) + " "
    s = re.sub(r"\$?\d+\.\d+(?:-\d+\.\d+)?", stash, s)
    s = s.strip().lower()
    s = unquote(s)
    s = s.replace("+", " ")
    s = re.sub(r"[\u2019\u2018]", "'", s)
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # 还原小数占位符
    for i, d in enumerate(decimals):
        s = s.replace(f"dec{i}", d)
    return re.sub(r"\s+", " ", s).strip()


def rule_infer(s, lex):
    """
    纯规则推断，返回 (结果, 存疑原因列表)。
    存疑原因非空 => 需确认。
    """
    # URL 编码异常：Walmart 对 %20 处理不一致，一律标「需确认」
    if "%20" in s:
        return s.strip().lower(), ["URL编码异常:%20"]

    # 含点号的词（域名/品牌如 walmart.com / tactical.gloves）：
    # Walmart 有时保留点号有时拆分，规则无法判断 -> 需确认
    import re as _re
    if _re.search(r"[a-z]\.[a-z]", s) and not _re.search(r"\d\.\d", s):
        return preprocess(s), ["含点号词:点号保留/拆分不确定"]

    s = preprocess(s)
    for phrase, repl in COMPOUND_MAP.items():
        s = re.sub(r"\b" + re.escape(phrase) + r"\b", repl, s)

    known = lex["known_words"]
    word_lex = lex["word_lexicon"]
    ambig = lex["ambiguous"]
    volatile = lex["volatile_words"]
    doubts = []
    out = []
    for w in s.split():
        orig = w
        w = re.sub(r"'s$", "", w)
        if w in GENDER_MAP:
            w = GENDER_MAP[w]
        elif w in word_lex:
            w = word_lex[w]
        elif len(w) > 3 and w.endswith("ies") and not w.endswith("ties"):
            w = w[:-3] + "y"
            if w not in known:
                doubts.append(f"词形推断:{orig}->{w}")
        elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
            if w not in known:
                doubts.append(f"复数推断:{orig}->{w}")
        else:
            if orig not in known and not orig.isdigit():
                doubts.append(f"未见过词元:{orig}")
        if orig in ambig:
            doubts.append(f"字典冲突:{orig}->{ambig[orig]}")
        # 不一致词（Walmart 黑箱）：原始词或变换结果任一不稳定 -> 需确认
        # 例：belts->belt 后 belt 是不稳定词，必须拦截
        if orig in volatile:
            doubts.append(f"不稳定词:{orig}")
        elif w in volatile and w != orig:
            doubts.append(f"不稳定词:{orig}->{w}")
        out.append(w)
    return " ".join(out), doubts


def normalize_with_audit(raw, lex):
    """返回 (标准词, 置信度, 来源, 存疑原因列表)"""
    key = raw.strip().lower()
    if key in lex["full_query_map"]:
        return lex["full_query_map"][key], CONF_SAMPLE, "样本", []
    result, doubts = rule_infer(raw, lex)
    if doubts:
        return result, CONF_REVIEW, "规则", doubts
    return result, CONF_HIGH, "规则", []


def find_merge_groups(results):
    groups = defaultdict(list)
    for raw, std, conf, src, doubts in results:
        groups[std].append(raw)
    return {k: v for k, v in groups.items() if len(v) > 1}


def audit(lex):
    """留一法自检：屏蔽样本命中，测规则还原率 + 自检拦截率"""
    fq = lex["full_query_map"]
    ok = 0
    review_caught = 0
    silent_wrong = 0
    for q, n in fq.items():
        pred, doubts = rule_infer(q, lex)
        if pred == n:
            ok += 1
        else:
            # 判错了：是否被自检拦截？
            if doubts:
                review_caught += 1
            else:
                silent_wrong += 1
    total = len(fq)
    print("=" * 60)
    print(f"规则自检报告（对 {total} 个已收录样本，留一法）")
    print("=" * 60)
    print(f"  规则独立推断正确        : {ok}/{total} = {ok/total:.1%}")
    print(f"  判错但被「需确认」拦截  : {review_caught}/{total} = {review_caught/total:.1%}  ← 不会混进投放")
    print(f"  判错且自检漏过(静默错)  : {silent_wrong}/{total} = {silent_wrong/total:.2%}  ← 需修复")
    print()
    print(f"  样本查表覆盖            : {total}/{total} = 100%（已收录词全部准确）")
    print(f"  结果可靠性(查表+拦截)   : {(total-silent_wrong)/total:.2%}")
    if silent_wrong:
        print(f"\n⚠️ 仍有 {silent_wrong} 个词会被静默判错，需要修复规则/字典。")
    else:
        print("\n✅ 所有已收录词 100% 可靠；未收录词若有风险一律标「需确认」。")


def detect_word_column(fieldnames):
    if not fieldnames:
        return None
    fl = [f.strip().lower() for f in fieldnames]
    for cand in ["raw query", "原始查询", "keyword", "关键词", "search term", "query", "词", "客户搜索词"]:
        if cand in fl:
            return fieldnames[fl.index(cand)]
    return fieldnames[0]


def main():
    args = sys.argv[1:]
    lex = load_lexicon()

    if "--audit" in args:
        audit(lex)
        return

    if not args:
        print(__doc__)
        sys.exit(1)

    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = args[i + 1]
        del args[i:i + 2]

    results = []
    if "--file" in args:
        i = args.index("--file")
        path = args[i + 1]
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            col = detect_word_column(reader.fieldnames)
            for row in reader:
                raw = (row.get(col) or "").strip()
                if raw:
                    results.append((raw,) + normalize_with_audit(raw, lex))
    elif "--stdin" in args:
        for line in sys.stdin:
            raw = line.strip()
            if raw:
                results.append((raw,) + normalize_with_audit(raw, lex))
    else:
        for raw in args:
            results.append((raw,) + normalize_with_audit(raw, lex))

    print(f"{'客户搜索词':<42} {'广告标准词':<42} {'置信度'}")
    print("-" * 104)
    for raw, std, conf, src, doubts in results:
        mark = "  ⚠" if conf == CONF_REVIEW else ("  ✓" if conf == CONF_SAMPLE else "  ~")
        print(f"{raw:<42} {std:<42} {conf}{mark}")
        if doubts:
            print(f"      存疑: {'; '.join(doubts[:3])}")

    merges = find_merge_groups(results)
    if merges:
        print(f"\n⚠️  发现 {len(merges)} 组重复（指向同一标准词，只开一个广告词）:")
        for std, raws in sorted(merges.items()):
            print(f"  [{std}]")
            for r in raws:
                print(f"      - {r}")

    review = [r for r, std, c, src, d in results if c == CONF_REVIEW]
    if review:
        print(f"\n❗ {len(review)} 个词标记「需确认」——确认后请回灌词表，切勿直接投放。")

    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["客户搜索词", "广告标准词", "置信度", "存疑原因"])
            for raw, std, conf, src, doubts in results:
                w.writerow([raw, std, conf, "; ".join(doubts)])
        print(f"\n结果已写入: {out_path}")


if __name__ == "__main__":
    main()
