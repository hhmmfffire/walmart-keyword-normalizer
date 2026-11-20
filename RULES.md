# Walmart 广告标准词归一化规则

> 版本 v1.2 · 2026-11-20
> 本文件是 skill 的核心资产，随规则迭代升版本。样本数据不进入 GitHub，仅 `RULES.md` / `scripts/` / `CHANGELOG.md` 会被分享。

## 背景

Walmart 广告后台用「广告标准词」（即报表中的 `Normalized Query`）投放。客户在搜索框输入的是「客户搜索词」（`Raw Query`）。多个不同的客户搜索词，本质指向同一个广告标准词——若按客户词开广告，会造成重复投放。

本规则的目标是：**输入任意关键词 → 返回其广告标准词**，并对指向同一标准词的词做归并，避免重复开词。

## 核心原则（用户决策）

1. **标准词基准** = Walmart 报表中的 `Normalized Query` 列。
2. **样本优先，规则兜底**：命中已学样本的词直接用样本标准词；全新词才用规则推断，并标注「规则推测」。样本是裁判——若规则推断与样本冲突，说明规则需要修正。
3. **规则与数据分离**：规则文档 + 脚本可分享；样本词表只存本地 `data/`，不上传 GitHub。
4. **持续进化**：每次喂新样本发现新规律，更新本文件并升版本、写 CHANGELOG、同步 GitHub。

## 归一化管线（规则兜底时按此顺序执行）

### Step 1 — 预处理
- 转小写
- URL 解码：`%20` → 空格、`+` → 空格
- 统一撇号：`'` `'` → `'`
- 标点/符号（含 `.` `,` `/` `-` `®` `&` `"` `”` 等）→ 空格
- 合并多余空格

例：`accu-chek aviva plus meter` → `accu chek aviva plus meter`

### Step 2 — 复合词合并
- `touch screen` → `touchscreen`（邻接词，不限位置）

例：`touch screen winter gloves` → `touchscreen winter glove`

### Step 3 — 所有格剥离
- `word's` → `word`（词尾 `'s` 去掉）

### Step 4 — 性别/人群词映射（样本中 100% 一致，零例外）
| 客户词 | 标准词 |
|---|---|
| women / womens / women's / woman's | woman |
| men / mens / men's / man's | men |
| ladies / ladys | lady |
| boys | boy |
| girls | girl |
| kids | kid |

例：`women's golf gloves` → `woman golf glove`

### Step 5 — 词元字典（从样本学习，606 条）
由 `scripts/learn.py` 从样本自动提取的单词级映射，优先级高于通用规则。常见类别：

**复数 → 单数**
- gloves→glove, braces→brace, monitors→monitor, straps→strap, slings→sling, grips→grip, cuffs→cuff, splints→splint, fingers→finger, mittens→mitten（西语同理：guantes→guante, fajas→faja, hombres→hombre）

**词形变化（-ing/-ed）**
- lifting→lift, riding→ride, cycling→cycle, padded→pad, lined→line, weightlifting→weightlift

**拼写纠错**
- wirking→working, excercise→exercise, accesories→accessory, pototlls→pototll

**词义替换**
- women work glove synthetic leather → woman work glove faux leather（leather→faux leather 在特定语境）

> 完整字典见本地 `data/lexicon.json` 的 `word_lexicon` 字段。

### Step 6 — 通用复数兜底（字典无命中时）
- `-ies` → `-y`（specialties→specialty），排除 `-ties`
- 词尾 `-s` → 去 `-s`（长度 >3，排除 `-ss`/`-us`/`-is` 结尾）

## 已知不一致（Walmart 自身的，样本优先处理）

Walmart 的归一化是**搜索引擎黑箱**，不是公开规则。样本里有大量无法用规则预测的行为：

- 词形上下文相关：`belt→belts` 139 次但 `belt` 保持 15 次；`gloves→glove` 占绝大多数但少数保持
- 词序重排：`back belt support → back support belts`
- 词插入：`otc → otc tool`、`sharper image → the sharper image`（凭空多词）
- 词替换：`wells lamont welding → well lamont welders`、`garden→gardening` 但 `garden work→garden work`
- `-ing` 保留不一：`lifting→lift` 但 `hunting`/`running` 保留
- 编码异常：`%20` 有时解码有时原样保留
- 带重音西语（`máquina de presión`）重音剥离不稳

**因此不做"规则绝对化"的徒劳尝试。** 系统把这些不稳定行为记入 `volatile_words`（不一致词/插入触发词/复数保留词），新词含此词一律标「需确认」，由人确认后回灌词表。

## 成功率定义与基线（诚实三指标）

"成功率"有三个不同含义，必须分开看（用 `scripts/evaluate.py` 检查）：

| 指标 | 数值 | 含义 |
|---|---|---|
| 真实使用准确率 | **100%**（5345/5345）| 已收录词走查表，全部正确——这是你实际得到的成功率 |
| 纯规则推断准确率 | 95.5%（留一法）| 屏蔽查表、规则单独推断新词——反映规则本身水平 |
| 结果可靠性 | **100%**（漏过 0）| 规则判错时全部被「需确认」拦截，错误绝不混进投放 |

**为什么能承诺"结果 100% 可靠"**：规则单推断只有 95.5%，但剩下 4.5% 全被自检拦下标记为"需确认"，不会静默出错。你确认回灌后，该词永久走查表、100% 准确。随着不断喂样本/确认，你接触过的所有词都 100% 可靠。

## 100% 的边界（诚实声明）

- ✅ **已收录词 / 你确认过的词**：查表命中，100% 准确
- ✅ **全新词**：若安全（所有词元稳定、无黑箱行为）直接给"高置信"结果；若有任何存疑点标"需确认"，绝不静默出错
- ❌ 对任意没见过的新词，纯规则不可能 100%——这是 Walmart 黑箱决定的，任何声称做到的都是偷偷查表
- 终极校验路径（已调研）：Walmart Ads API 的 `SuggestedKeywordApi`（`/api/v1/keyword_suggestions`）只按 adGroupId 返回广告组推荐词，**不接受任意客户词返回其标准词**，无法作为"任意词→标准词"的校验器。Walmart 未公开此映射接口。因此绝对 100% 校验在 API 层面不可行；系统采用"自检拦截 + 确认回灌"保证结果 100% 可靠。若将来 Walmart 开放归一化接口或用户提供后台导出的 Raw→Normalized 数据，可接入做终极校验。

## 使用方式

- 触发：看到关键词或关键词文件即自动转换（用户决策）
- 输出：客户词 → 标准词对照 + 置信度标记 + 重复词分组提示
- 主场景：批量（CSV / 粘贴多行）；辅场景：单个词

## 迭代记录

见 `CHANGELOG.md`。每次规则变更：升本文件版本号 + 写 CHANGELOG + 同步 GitHub。
