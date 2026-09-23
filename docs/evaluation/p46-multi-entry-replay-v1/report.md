# 同类字段多条目：离线回放

6份原失败输出与2份原成功输出均通过新协议提交、持久化、加载及报告检查，59个条目按原顺序保留。
这是已保存动作的离线兼容性测试，不是新模型成功率；原始真实评测仍为2/8。付费调用0，网络连接被禁止。
多条目尚未建立实验关联，因此比较不自动排名；不修复原有引用或类型错误。

| 样本 | 原诊断 | 新协议诊断 | 保留条目 |
|---|---|---|---|
| ontology_parser | schema_invalid | accepted | 7 |
| speech_recognition | accepted | accepted | 2 |
| event_extraction | schema_invalid | accepted | 9 |
| mobile_robot | accepted | accepted | 5 |
| many_languages_parser | schema_invalid | accepted | 9 |
| contextual_lstm | schema_invalid | accepted | 9 |
| russian_twitter | schema_invalid | accepted | 9 |
| entity_coreference | schema_invalid | accepted | 9 |
