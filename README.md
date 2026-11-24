# Walmart 广告标准词归一化 Skill

把 Walmart 客户搜索词（Raw Query）转换为广告标准词（Normalized Query），避免因多个客户词指向同一标准词而重复开广告。

## 决策基线（v2.0）
- 标准词基准 = Walmart 报表的 `Normalized Query`
- **全部自动判断**：样本走查表；新词走 9 级自动判断管线（字典/纠错/缩写/复数/西语/虚词/放行）。没有「需确认」——skill 的价值就是由 AI 把所有词判断完
- 规则可分享，样本数据只留本地
- 输入任意词/文件 → 返回标准词 + 判断依据 + 重复词归并提示

## 文件结构
```
walmart-keyword-normalizer/
├── SKILL.md          # skill 定义与工作流
├── RULES.md          # 归一化规则文档（核心资产，随迭代升版本）
├── CHANGELOG.md      # 规则变更记录
├── README.md         # 本文件
├── scripts/
│   ├── normalize.py  # 转换引擎（查表 + 9级自动判断 + 重复检测）
│   ├── learn.py      # 从新样本学习词元字典 + 不稳定词检测
│   ├── evaluate.py   # 成功率检查（三个分开的指标）
│   └── confirm.py    # 可选回灌（发现判断不准时修正）
└── data/             # 本地样本数据，不进 GitHub
    └── lexicon.json  # 词元字典 + 查询映射 + 不稳定词表
```

## 使用
依赖：Python 3（标准库，无需额外安装）

```bash
# 单个/多个词
python scripts/normalize.py "back braces for women" "mens golf gloves"

# 批量 CSV
python scripts/normalize.py --file keywords.csv --out result.csv

# 检查成功率
python scripts/evaluate.py
python scripts/evaluate.py --file goldset.csv   # 自定义金标准

# 喂新样本更新字典（样本只存本地）
python scripts/learn.py "D:/新样本/*.csv"

# 可选回灌（发现某词判断不准时修正）
python scripts/confirm.py "客户词" "确认的标准词"
```

## 成功率（v2.0 基线）
| 指标 | 数值 | 含义 |
|---|---|---|
| 已收录词准确率 | 100% | 走查表，全对 |
| 新词自动判断准确率 | 96.9% | 屏蔽查表的压力测试 |
| 自动判断覆盖率 | 100% | 任意词都自动出结果，零人工 |

自动判断规律（9 级）：词元字典 > 纠错词典（moniter→monitor 等）> 缩写（mon→monitor）> 性别 > 虚词放行 > 粘连词拆分（bloodpressure→blood pressure）> 西语去音（presión→presion）> 编辑距离纠错 > 原样放行。实测 236 个真实搜索词需确认从 39 降到 0。
诚实说明：Walmart 归一化含黑箱（词序重排/插词），纯规律对全新词不可能绝对 100%，但常见情况已用固化规律覆盖；判断依据列透明标注便于抽查。

## 迭代
发现新规律 → 更新 `RULES.md` 版本号 → 写 `CHANGELOG.md` → 重新 learn → evaluate 验证 → 同步 GitHub。
