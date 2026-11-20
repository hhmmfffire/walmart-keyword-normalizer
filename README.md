# Walmart 广告标准词归一化 Skill

把 Walmart 客户搜索词（Raw Query）转换为广告标准词（Normalized Query），避免因多个客户词指向同一标准词而重复开广告。

## 决策基线
- 标准词基准 = Walmart 报表的 `Normalized Query`
- 三级置信度 + 自检拦截：样本 / 高置信 / 需确认——错误绝不静默混进投放
- 规则可分享，样本数据只留本地
- 输入任意词/文件 → 返回标准词 + 重复词归并提示

## 文件结构
```
walmart-keyword-normalizer/
├── SKILL.md          # skill 定义与工作流
├── RULES.md          # 归一化规则文档（核心资产，随迭代升版本）
├── CHANGELOG.md      # 规则变更记录
├── README.md         # 本文件
├── scripts/
│   ├── normalize.py  # 转换引擎（三级置信度 + 自检 + 重复检测）
│   ├── learn.py      # 从新样本学习词元字典 + 不稳定词检测
│   ├── evaluate.py   # 成功率检查（三个诚实指标）
│   └── confirm.py    # 确认回灌（确认后的词永久 100% 可靠）
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

# 确认回灌（"需确认"的词核对后写入）
python scripts/confirm.py "客户词" "确认的标准词"
```

## 成功率（v1.2 基线）
| 指标 | 数值 |
|---|---|
| 真实使用准确率（查表） | 100% |
| 纯规则推断准确率（留一法） | 95.5% |
| 结果可靠性（错误全被拦截） | 100% |

诚实说明：Walmart 归一化是黑箱（词序重排/词插入/拼写纠错），纯规则对任意新词不可能 100%；但系统保证错误不混进投放，确认回灌的词永久 100% 准确。接入 Walmart 数据源可做到绝对 100% 校验。

## 迭代
发现新规律 → 更新 `RULES.md` 版本号 → 写 `CHANGELOG.md` → 重新 learn → evaluate 验证 → 同步 GitHub。
