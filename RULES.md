# Walmart 广告标准词归一化规则

> 版本 v2.0 · 2026-11-24
> 本文件是 skill 的核心资产，随规则迭代升版本。样本数据不进入 GitHub，仅 `RULES.md` / `scripts/` / `CHANGELOG.md` 会被分享。
>
> **v2.0 重大变更**：从「查表 + 需确认拦截」升级为「查表 + 全部自动判断」。
> 用户决策：不要人工判断——skill 的意义就是由 AI 把所有词判断完，直接返回可投放的标准词。
> v1.x 的「需确认」状态已取消，所有词自动出结果，详见下方「自动判断规则」章节。

## 背景

Walmart 广告后台用「广告标准词」（即报表中的 `Normalized Query`）投放。客户在搜索框输入的是「客户搜索词」（`Raw Query`）。多个不同的客户搜索词，本质指向同一个广告标准词——若按客户词开广告，会造成重复投放。

本规则的目标是：**输入任意关键词 → 返回其广告标准词**，并对指向同一标准词的词做归并，避免重复开词。

## 核心原则（用户决策）

1. **标准词基准** = Walmart 报表中的 `Normalized Query` 列。
2. **样本优先，自动判断兜底**：命中已学样本的词直接用样本标准词；全新词用 v2.0 自动判断管线（字典→纠错→缩写→复数→放行）推断，直接给出可投放结果，**不再抛回人工确认**。样本是裁判——若自动判断与样本冲突，说明规则需要修正。
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
- **安全约束**：仅在词干已在标准词库时才变形，避免 `diabetes→diabete` 这类误伤

### Step 7 — 自动判断层（v2.0 新增，取代「需确认」）
未命中样本的词按下列顺序自动判断，保证任意输入都出结果：

| 优先级 | 规则 | 例 |
|---|---|---|
| 1 | 词元字典映射（Walmart 真实归一，最高优先） | alphamed→alphame, approved→approve |
| 2 | 固化拼写纠错词典 | moniter→monitor, ciff→cuff, omoron→omron, expancve→expensive, uper→upper, daul→dual, masion→machine |
| 3 | 缩写展开 | mon→monitor |
| 4 | 性别词 | womens→woman |
| 5 | 虚词放行（the/i/will/w/that/how 等） | 原样保留 |
| 6 | 粘连词拆分 | bloodpressure→blood pressure, upperarm→upper arm |
| 7 | 西语重音剥离（NFKD） | presión→presion, máquina→maquina |
| 8 | 编辑距离纠错（cutoff 0.88，排除 -al/-ic/-ly 等正常构词） | 明显错拼自动纠，正常词不误伤 |
| 9 | 未见过词元原样放行 | Walmart 对无问题的新词就是保留原样 |

**设计理由**：Walmart 报表样本证实其归一化本身就会纠错（armohada→almohada、punk→pink、excercise→exercise、machanics→mechanic），所以自动纠错符合平台口径；正常新词（oxygen/android/measurement）原样放行也符合样本表现。

## 已知不一致（Walmart 自身的，样本优先处理）

Walmart 的归一化是**搜索引擎黑箱**，不是公开规则。样本里有大量无法用规则预测的行为：

- 词形上下文相关：`belt→belts` 139 次但 `belt` 保持 15 次；`gloves→glove` 占绝大多数但少数保持
- 词序重排：`back belt support → back support belts`
- 词插入：`otc → otc tool`、`sharper image → the sharper image`（凭空多词）
- 词替换：`wells lamont welding → well lamont welders`、`garden→gardening` 但 `garden work→garden work`
- `-ing` 保留不一：`lifting→lift` 但 `hunting`/`running` 保留
- 编码异常：`%20` 有时解码有时原样保留
- 带重音西语（`máquina de presión`）重音剥离不稳

**v1.x 做法**（已弃用）：把这些不稳定行为记入 `volatile_words`，新词含此词标「需确认」由人确认。
**v2.0 做法**：用户明确不要人工判断。这些黑箱词一旦在样本里出现过就走查表（100%）；全新词含黑箱模式时按最可信规律自动判断并给出结果，同时在「判断依据」里透明标注，不阻塞投放。

## 成功率定义与基线（v2.0 诚实三指标）

"成功率"有三个不同含义，必须分开看（用 `scripts/evaluate.py` 检查）：

| 指标 | 数值 | 含义 |
|---|---|---|
| 已收录词准确率 | **100%**（5345/5345）| 已收录词走查表，全部正确 |
| 新词自动判断准确率 | 96.9%（留一法）| 屏蔽查表、纯规律推断——反映规则水平。人为压力测试，不代表真实使用 |
| 自动判断覆盖率 | **100%** | 任意词都自动返回标准词，零人工介入——这是 v2.0 的核心承诺 |

**为什么要"全部自动判断"**：用户决策——若还要人工确认，skill 就失去意义。v2.0 用 Step 7 的 9 级规律把拼写错误、缩写、粘连词、西语、虚词、新词全部自动化，实测 236 个真实搜索词（ALPHAGOMED 血压计报告）从 39 个需确认降到 0，全部直接可投放。

## 100% 的边界（诚实声明）

- ✅ **已收录词**：查表命中，100% 准确
- ✅ **任意新词**：v2.0 全部自动给出标准词，零人工；含拼写/缩写/粘连词/西语/虚词的词按固化规律纠正，无问题的新词原样放行
- ⚠️ **Walmart 黑箱词**：词序重排/凭空插词（如 `otc→otc tool`）这类无通用规律的行为，全新词无法保证 100% 命中平台原始口径；但这些词一旦在样本出现即查表 100%。判断依据会透明标注，便于抽查
- 终极校验路径（已调研，不可用）：Walmart Ads API 的 `SuggestedKeywordApi`（`/api/v1/keyword_suggestions`）只按 adGroupId 返回广告组推荐词，**不接受任意客户词返回其标准词**，无法作为校验器。Walmart 未公开此映射接口。若将来开放或用户提供后台 Raw→Normalized 数据，可接入做终极校验。

## 使用方式

- 触发：看到关键词或关键词文件即自动转换（用户决策）
- 输出：客户词 → 标准词对照 + 来源标记（样本/自动判断）+ 判断依据 + 重复词分组提示
- 主场景：批量（CSV / 粘贴多行）；辅场景：单个词
- **所有词直接可投放，无「需确认」拦截**（v2.0）

## 迭代记录

见 `CHANGELOG.md`。每次规则变更：升本文件版本号 + 写 CHANGELOG + 同步 GitHub。
