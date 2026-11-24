# 变更日志（CHANGELOG）

记录每次归一化规则的更新：日期 / 版本号 / 改了什么 / 由哪份样本触发。

格式：
```
## vX.Y (YYYY-MM-DD)
- 变更：...
- 触发样本：...
- 影响：...
```

---

## v2.0 (2026-11-24)
- 重大变更：取消「需确认」状态，改为全部自动判断——用户明确"不要人工判断，skill 的意义就是由 AI 全部判断、自行找规律"
- 新增自动判断层（normalize.py Step 7，9 级优先级）：词元字典 > 固化纠错词典 > 缩写 > 性别 > 虚词放行 > 粘连词拆分 > 西语去音(NFKD) > 编辑距离纠错(cutoff 0.88,排除正常构词后缀) > 原样放行
- 新增固化纠错词典：moniter/ciff/omoron/expancve/uper/daul/masion/oressure/peessure 等深度错拼
- 新增粘连词拆分：bloodpressure→blood pressure、upperarm→upper arm；缩写 mon→monitor
- 预处理加西语重音剥离（presión→presion），与 Walmart 样本口径一致
- 复数变形加安全约束（仅词干在标准词库才变），避免 diabetes→diabete 误伤
- normalize_with_audit 不再返回 CONF_REVIEW，全部标「样本」或「自动判断」，均可投放
- evaluate.py 三指标更新：已收录词准确率100% / 新词自动判断96.9% / 自动判断覆盖率100%
- 触发样本：ALPHAGOMED 血压计搜索词报告（236 唯一词），需确认从 39 降到 0
- 影响：236 词全部自动出标准词，去重后 216 个可投放词；无需任何人工确认

## v1.3 (2026-11-24)
- 修复严重 bug：插入触发词检测误把「后一个词」记为不稳定词，导致 `otc tool blood pressure` 中 `blood` 被污染，整个血压计类目词全被误标「需确认」
- 修正：插入触发词只取紧邻前词（`otc`）；仅当插入词是句首定冠词 `the` 时才取后词（`the sharper image`）
- 触发样本：ALPHAGOMED search_query_report_Merged.csv（血压计，300 词）——修复前 91 词需确认，修复后 39 词需确认
- 影响：可靠性仍 100%（漏过 0）；blood 不再污染；v1.2 生成的血压计结果若标大量"需确认"需用 v1.3 重跑

## v1.2 (2026-11-20)
- 新增成功率自检体系：evaluate.py 输出三个诚实指标（真实使用准确率 / 纯规则准确率 / 结果可靠性）
- 新增自检拦截机制：volatile_words（不一致词 + 插入触发词 + 复数保留词），新词含黑箱行为一律标「需确认」
- 新增 confirm.py：确认回灌闭环，确认后的词永久走查表 100% 可靠
- 修复预处理：小数保护（5.00 不被拆）、复合词（one-piece/armrest/waterproof）、URL 编码异常检测、点号词检测
- 达成指标：真实使用准确率 100%、结果可靠性 100%（漏过 0）、纯规则 95.5%
- 触发原因：用户要求"100% 成功率"，分析确认纯规则不可能 100%（Walmart 黑箱），改为"结果 100% 可靠"架构
- 影响：新增 3 个脚本（normalize.py 重写 / evaluate.py / confirm.py），learn.py 增加 volatile/quirk 学习

## v1.1 (2026-11-20)
- normalize.py 引入三级置信度（样本 / 高置信 / 需确认）与自检 audit
- learn.py 增加 known_words 字段

## v1.0 (2026-11-20)
- 初始化 skill，建立「规则文档 + 转换脚本 + CHANGELOG」结构
- 从 `D:\WM\KP汇总` 的 62 份样本（BL 44 份 + XYJ 2 份，共 5,345 组词对）学习归一化规律
- 确立核心原则：标准词基准 = Normalized Query；样本优先、规则兜底；规则与数据分离
- 归纳 6 步归一化管线：预处理 → 复合词合并 → 所有格剥离 → 性别词映射 → 词元字典 → 通用复数
- 学到 606 条词元映射，纯规则兜底准确率 95.8%（留一法），样本查表 100%
- 触发样本：KP汇总 全量
- 影响：建立基线，后续新规则在此之上迭代
