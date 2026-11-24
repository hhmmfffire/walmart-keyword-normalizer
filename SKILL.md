---
name: walmart-keyword-normalizer
description: 把 Walmart 客户搜索词（Raw Query）转换为广告标准词（Normalized Query），归并指向同一标准词的词，避免重复开广告。当用户消息中出现英文/Walmart 关键词、关键词文件（CSV/Excel），或要求"转标准词/归一化关键词/查广告词/去重关键词"时自动触发。适合 Walmart 广告投放前的关键词清洗。
---

# Walmart 广告标准词归一化

## 用途
Walmart 广告用「广告标准词」投放。多个客户搜索词本质指向同一标准词，直接按客户词开广告会重复投放。本 skill 把任意关键词转成标准词，并检测重复。

## 触发规则
**自动触发**（用户决策）：
- 用户消息中出现英文关键词或关键词列表时，主动转换并返回标准词
- 用户直接贴 CSV/Excel 关键词文件时，自动批量处理
- 用户说"转标准词 / 归一化 / 查广告词 / 去重关键词"等明确指令时

用户纯讨论其他话题时不要插手转换。

## 核心决策（务必遵守）
1. **标准词基准** = Walmart 报表的 `Normalized Query` 列。
2. **样本优先 + 全部自动判断**（v2.0，用户明确不要人工判断）：
   - 命中样本 `full_query_map` → 标记「样本」（100% 可靠）
   - 未命中 → 走自动判断管线（字典→纠错→缩写→性别→虚词放行→粘连词拆分→西语去音→编辑距离纠错→放行），标记「自动判断」，**直接可投放**
   - **没有「需确认」状态**——skill 的价值就是由 AI 把所有词判断完，不把判断抛回用户
   - 样本是裁判：自动判断与样本冲突即说明规则要修
3. **输出必须包含合并关系**：客户词 → 标准词对照 + 来源 + 判断依据 + 重复词分组（避免重复开词）。用户操作链：拿标准词 → 查重 → 判相关性 → 批量上传。
4. **批量为主，单词为辅**。
5. **自动判断规律**：拼写纠错（moniter→monitor/ciff→cuff/omoron→omron）、缩写（mon→monitor）、粘连词拆分（bloodpressure→blood pressure）、西语去音（presión→presion）、虚词放行、正常新词原样保留。详见 RULES.md Step 7。

## 使用方法

脚本位置：`scripts/normalize.py`（依赖 Python 3 标准库）

### 单个/少量词
```bash
python "C:/Users/Administrator/.workbuddy/skills/walmart-keyword-normalizer/scripts/normalize.py" "back braces for women" "mens golf gloves"
```

### 批量 CSV
```bash
python ".../normalize.py" --file keywords.csv --out result.csv
```
CSV 自动识别词列（`Raw Query`/`关键词`/`keyword`/`query` 等，否则取第一列）。

### 用户直接粘贴多行词
把词写到临时文件或用 `--stdin` 处理。

## 输出解读
- 「样本」= 查表命中，100% 可靠，可投放
- 「自动判断」= 规则/纠错自动得出的标准词，**直接可投放**（判断依据列显示做了什么处理）
- 「⚠️ 发现 N 组重复」= 这些客户词指向同一标准词，**只开一个广告词**

## 成功率检查（用户关心"100%"时必读）
用 `scripts/evaluate.py` 检查，它会输出三个分开的指标：
```bash
python ".../scripts/evaluate.py"
python ".../scripts/evaluate.py --file goldset.csv"   # 自定义金标准验证
```
- **已收录词准确率 100%**：已收录词走查表全对
- **新词自动判断准确率 96.9%**：屏蔽查表的压力测试，反映规则水平（Walmart 黑箱导致纯规则不可能 100%）
- **自动判断覆盖率 100%**：任意词都自动出结果，零人工介入——v2.0 核心承诺

对用户诚实说明：v2.0 全部自动判断，不再抛"需确认"。Walmart 归一化含黑箱（词序重排/词插入/拼写纠错），纯规律对全新词不可能绝对 100%，但拼写/缩写/粘连词/西语等常见情况已用固化规律覆盖，实测真实词表需确认从 39 降到 0。判断依据列透明标注便于抽查。若用户能提供 Walmart 后台 Raw→Normalized 数据，可做绝对校验。

## 可选：确认回灌（仅当用户发现某词判断不准时）
用户发现自动判断不准，可提供正确标准词：
```bash
python ".../scripts/confirm.py "客户词" "确认的标准词"
```
写入后该词走查表，永久 100% 可靠。v2.0 下这是可选的修正手段，不再是常规流程。

## 喂新样本 / 规则迭代
当用户提供新的关键词样本表格，要求更新规则时：

1. 运行学习脚本更新本地字典（样本只存本地，不进 GitHub）：
   ```bash
   python ".../scripts/learn.py" "D:/新样本/*.csv"
   ```
2. 运行 `evaluate.py` 检查三项成功率指标，定位失败样例
3. 更新 `RULES.md`：加入新规则 / 修正规则，升级版本号
4. 在 `CHANGELOG.md` 追加：日期、版本、改了什么、由哪份样本触发
5. 同步到 GitHub 私有仓库 `walmart-keyword-normalizer`（只推 RULES.md / CHANGELOG.md / SKILL.md / README.md / scripts/，**绝不推 data/ 里的样本数据**）

## 详细规则
见 `RULES.md`。归一化管线：预处理（含西语去音）→ 复合词合并 → 所有格剥离 → 性别词映射 → 词元字典 → 复数兜底 → **自动判断层（v2.0，9 级优先级，取代需确认）**。Walmart 自身的不一致（如 `belt→belts`）靠样本查表兜底。
