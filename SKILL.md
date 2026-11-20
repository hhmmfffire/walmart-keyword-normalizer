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
2. **三级置信度 + 自检拦截**（保证结果 100% 可靠）：
   - 命中样本 `full_query_map` → 标记「样本」（100% 可靠）
   - 新词但所有词元稳定、无黑箱行为 → 标记「高置信」（自检通过）
   - 新词含未见过词元 / 不一致词 / 插入触发词 / 编码异常 → 标记「需确认」，**禁止直接投放**
   - 样本是裁判：规则与样本冲突即说明规则要修
3. **输出必须包含合并关系**：客户词 → 标准词对照 + 置信度 + 重复词分组（避免重复开词）。用户操作链：拿标准词 → 查重 → 判相关性 → 批量上传。
4. **批量为主，单词为辅**。
5. **可靠性承诺**：错误绝不静默混进投放——所有可疑结果一律"需确认"，用户确认回灌后永久 100% 可靠。

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
- 「样本」/「高置信」= 可直接用于投放
- 「需确认 ⚠」= 规则不可靠（含黑箱行为），**禁止直接投放**，核对后回灌
- 「⚠️ 发现 N 组重复」= 这些客户词指向同一标准词，**只开一个广告词**

## 成功率检查（用户关心"100%"时必读）
用 `scripts/evaluate.py` 检查，它会输出三个诚实指标：
```bash
python ".../scripts/evaluate.py"
python ".../scripts/evaluate.py --file goldset.csv"   # 自定义金标准验证
```
- **真实使用准确率 100%**：已收录词走查表全对
- **纯规则准确率 95.5%**：规则单独推断新词的水平（Walmart 黑箱导致不可能 100%）
- **结果可靠性 100%**：判错的词全被"需确认"拦截，零漏过

对用户要诚实说明：纯规则对任意新词不可能 100%（Walmart 归一化是含词序重排/词插入/拼写纠错的黑箱），但系统保证错误不混进投放；确认回灌的词永久 100% 准确。若用户能提供 Walmart 后台/API 数据源，可做绝对 100% 校验。

## 确认回灌闭环
"需确认"的词经用户核对后：
```bash
python ".../scripts/confirm.py "客户词" "确认的标准词"
```
写入后该词走查表，永久 100% 可靠，版本自动递增。

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
见 `RULES.md`。归一化管线 6 步：预处理 → 复合词合并 → 所有格剥离 → 性别词映射 → 词元字典 → 通用复数兜底。Walmart 自身的不一致（如 `belt→belts`）靠样本查表兜底。
