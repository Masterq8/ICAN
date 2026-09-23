# P4.6 新论文定向质量验收

本轮质量检查已执行：8 篇新论文成功提交 2 篇。具体失败原因见逐篇诊断；本报告不自动判定产品验收通过。

**语义审核尚未经人类确认。以下支持率、归类率和缺失率均为暂定值。**
AI 复核状态：completed；审核身份：assistant。

复核过程与分歧裁定见 [AI复核记录](review-adjudication.md)。
额外语义审核：16 次 deepseek-v4-pro，与下文原始生成用量分开计算，未重新生成卡片。

## 预先约定口径：成功提交样本

- 工具提交成功率：25.0%（2/8）
- 原文支持率：100.0%（7/7）
- 字段归类正确率：85.7%（6/7）
- 缺失字段识别率：87.5%（7/8）
- 已有字段槽位覆盖率：60.0%（6/10）

字段分母仅来自 2 篇成功卡片；不可把该口径解读为整体可靠。

## 补充口径：全部可解析原始草稿（事后增加）

- 工具提交成功率：25.0%（2/8）
- 原文支持率：93.2%（55/59）
- 字段归类正确率：88.1%（52/59）
- 缺失字段识别率：87.5%（14/16）
- 已有字段槽位覆盖率：82.1%（46/56）

字段指标统计全部可解析原始草稿中的字段，包括因重复字段而被 schema 拒绝的草稿；规则未改写原始输出。
槽位覆盖只表示字段名出现，不要求该字段内容支持且正确；它不是正确内容召回率。

用量：8 次 deepseek-flash；15508 输入 token、8724 输出 token。供应商未返回实际费用。

## 逐篇诊断

| 样本 | 工具诊断 | 运行状态 | 提交字段 | 遗漏的已有字段 | 规则提示 |
|---|---|---|---|---|---|
| ontology_parser | schema_invalid | failed | task, model, dataset, input_setting, training, result×2 | metric, limitation | — |
| speech_recognition | accepted | completed | limitation, model | task, input_setting, metric, result | — |
| event_extraction | schema_invalid | failed | task, dataset, metric×2, result×3, limitation, input_setting | model, training | — |
| mobile_robot | accepted | completed | task, model, input_setting, training, result | — | — |
| many_languages_parser | schema_invalid | failed | task×2, training, model, metric, input_setting, limitation, result×2 | dataset | — |
| contextual_lstm | schema_invalid | failed | task, dataset×2, input_setting, training, metric, result×2, limitation | model | — |
| russian_twitter | schema_invalid | failed | task, model, dataset, input_setting, training, metric, result×2, limitation | — | — |
| entity_coreference | schema_invalid | failed | task, model, dataset×2, training, input_setting, metric×2, result | — | — |

## 工具错误细节

### ontology_parser: `schema_invalid`

- `fields`：Value error, Experiment field names must not repeat
- 重复字段：`result` × 2
- 原文不支持：#1 `task`
- 字段错分：#4 `input_setting` → `training`

### event_extraction: `schema_invalid`

- `fields`：Value error, Experiment field names must not repeat
- 重复字段：`metric` × 2、`result` × 3
- 原文不支持：#1 `task`、#9 `input_setting`
- 字段错分：#8 `limitation` → `result`、#9 `input_setting` → `training`

### many_languages_parser: `schema_invalid`

- `fields`：Value error, Experiment field names must not repeat
- 重复字段：`task` × 2、`result` × 2
- 字段错分：#1 `task` → `model`、#2 `task` → `dataset`

### contextual_lstm: `schema_invalid`

- `fields`：Value error, Experiment field names must not repeat
- 重复字段：`dataset` × 2、`result` × 2

### russian_twitter: `schema_invalid`

- `fields`：Value error, Experiment field names must not repeat
- 重复字段：`result` × 2
- 原文不支持：#1 `task`
- 字段错分：#4 `input_setting` → `training`

### entity_coreference: `schema_invalid`

- `fields`：Value error, Experiment field names must not repeat
- 重复字段：`dataset` × 2、`metric` × 2

## 字段混淆

- `input_setting->training`：3
- `limitation->result`：1
- `model->input_setting`：1
- `task->dataset`：1
- `task->model`：1

## 审核边界

审核使用模型实际收到的六条证据（每条最多 2200 字符）；本轮最大 2156 字符，无实际截断。原文支持要求引用为连续原文且语义支持字段值，大小写调整、移除文献标记等忠实归一化不等于伪造引用。

字段缺失只表示输入证据未出现，不等于全文未报告。九类字段仅可各出现一次的现有协议与多数据集、多结果输出冲突，是本轮主要阻断因素。下一步应在新协议设计中表示同类多个条目，并以离线原始输出回放测试验证；本轮结果不重跑或改记成功。

确定性规则只覆盖强词法冲突，未触发规则不证明字段正确。当前审核发现 7 处类型混淆，具体类别见上表；规则仅覆盖 dataset/metric/result。

源代码身份固定在 2937a56；run-seal.json 为运行完成后的首次归档封存。finalize 检查结果、trace、journal、源码快照和审核字段哈希，不产生模型调用。

人工复核：打开 manual-review.json，按 occurrence 对照 metrics.json 中 raw_fields 以及 human-review.md 的证据；保留绑定哈希，修改判断与理由后执行 finalize 重算。当前 human_review_status=pending。
