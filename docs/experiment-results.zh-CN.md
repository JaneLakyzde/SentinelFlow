# SentinelFlow 参数遍历与 DeepSeek 复核实验报告

## 1. 实验目标

本实验回答三个问题：

1. 确定性候选检测器能否以高 Recall 覆盖参数遍历 episode？
2. 正式配置在纯正常流量和合法分页上的误报率是多少？
3. 当高 Recall 候选保留分页相似行为时，DeepSeek 复核能否提高 Precision，
   且不降低 Recall？

实验日期为 2026-07-28。当前实验属于 development 与 pure-normal 验证，不是
validation 或 blind-test。

## 2. 系统配置

### 2.1 候选检测

正式配置为 `configs/parameter-enumeration.yaml` 版本 `1.1`：

- 窗口长度：60 秒；
- 窗口重叠：40 秒；
- 最少不同值：5；
- 最少数值：5；
- 最低序列比例：0.6；
- 最低固定步长比例：0.6；
- 随机高基数阈值：8；
- 最低失败响应比例：0.5；
- 正式配置在候选阶段抑制声明的分页参数。

分页消融配置为
`configs/parameter-enumeration-llm-ablation.yaml`，只将
`suppress_pagination_parameters` 改为 `false`，其余阈值与正式配置一致。

### 2.2 LLM

- 供应商：DeepSeek；
- 模型：`deepseek-v4-pro`；
- 接口：OpenAI-compatible Chat Completions；
- Base URL：`https://api.deepseek.com`；
- Thinking：关闭；
- Temperature：0；
- 输出格式：JSON Object；
- 最大输出：4096 Tokens；
- 超时：60 秒；
- Provider 重试：最多 2 次；
- Schema 修复尝试：最多 3 次；
- Skill：`audit-api-security` 版本 0.1.0。

模型输出依次通过 JSON、字段、类别、请求序号、证据类型和证据数值校验。非法
响应不会生成告警，并且不会作为有效结果继续缓存。

## 3. 数据集

数据来自相邻项目 `ad-scout/api_security_lab`。生成器模拟广告 SDK 初始化、
拉取、竞价通知、曝光和事件上报，并插入六类异常。

### 3.1 Development

- 随机种子：20260726；
- 虚拟客户端：12；
- 事件总数：3000；
- 正常事件：2646；
- 参数遍历事件：106；
- 参数遍历连续 episode：13；
- 其他异常：接口滥用 198、越权 11、调用序列异常 12、重放 13、参数异常 14。

API 日志与 Ground Truth 均为 3000 行，请求 ID 和序号逐行对齐。审计与 LLM
命令只读取 API 日志；Ground Truth 仅由独立 evaluator 在审计结束后读取。

### 3.2 Pure normal

纯正常分区包含：

- 从混合运行中筛出的 2646 条正常事件；
- 8 条 `page=1..8`、固定 `page_size=20`、HTTP 200 的合法分页事件；
- 总计 2654 条事件。

数据哈希和已知限制记录在
`datasets/ad-scout-20260726.manifest.json`。

## 4. 指标口径

- Episode Recall：至少一个候选/告警覆盖该连续参数遍历 episode；
- Target-event Recall：被候选/告警覆盖的参数遍历请求比例；
- Candidate Precision：至少覆盖一个参数遍历请求的候选数除以全部候选数；
- LLM Precision：真 `alert` 数除以全部 `alert` 数；
- Pagination event FPR：被候选/告警覆盖的合法分页请求比例；
- Normal event FPR：被候选/告警窗口覆盖的正常请求比例。

候选是窗口级对象，可能同时包含攻击片段附近的正常请求。因此候选级
Precision 为 100% 时，请求级正常事件 FPR 仍可能非零，两者不能混用。

## 5. Development 调参结果

初始正式配置使用 60 秒窗口和 10 秒重叠。保持其他阈值不变，仅调整重叠：

| 重叠 | 检出 episode | Episode Recall | 候选级 FP | Pure-normal 候选 |
|---:|---:|---:|---:|---:|
| 10 秒 | 11/13 | 84.62% | 0 | 0 |
| 20 秒 | 12/13 | 92.31% | 0 | 0 |
| 30 秒 | 12/13 | 92.31% | 0 | 0 |
| 40 秒 | 13/13 | 100% | 0 | 0 |

因此配置版本 1.1 选择 40 秒重叠。该选择必须在未来的独立 validation 和
blind-test 上重新检验，不能继续根据盲测结果调整。

## 6. 正式配置结果

### 6.1 Development

| 指标 | 结果 |
|---|---:|
| 候选数 | 13 |
| 候选 TP / FP | 13 / 0 |
| Candidate Precision | 100% |
| Episode Recall | 100% |
| Target-event Recall | 100% |
| 正常事件窗口覆盖 FPR | 1.1716% |

DeepSeek 对 13 个候选全部返回 `alert`：

- 复核成功：13/13；
- 错误：0；
- `abstain`：0；
- `benign`：0；
- `out_of_scope`：0；
- 置信度范围：0.85–0.95；
- 平均置信度：0.8915。

因为候选层没有候选级假阳性，LLM 后 Precision 仍为 100%，增益为 0。

### 6.2 Pure normal

| 指标 | 结果 |
|---|---:|
| 事件数 | 2654 |
| 候选数 | 0 |
| 正常事件 FPR | 0% |
| 合法分页事件数 | 8 |
| 分页事件 FPR | 0% |

正式配置在候选阶段直接抑制 `page` 等声明的分页参数，因此不调用 LLM。

## 7. LLM 分页消融

为了避免“候选阶段已经消除全部误报，导致无法测量 LLM 增益”，消融实验只
关闭分页预抑制，让合法分页进入候选。LLM 同时获得可信正常上下文：

- 路径 `/api/catalog`；
- `page` 为从 1 开始的页码；
- `page_size` 固定为 20；
- 预期响应为 HTTP 200。

| 指标 | 仅候选 | 候选 + DeepSeek |
|---|---:|---:|
| 候选/告警 | 14 | 13 |
| TP | 13 | 13 |
| FP | 1 | 0 |
| Precision | 92.86% | 100% |
| Episode Recall | 100% | 100% |
| Target-event Recall | 100% | 100% |
| Pagination event FPR | 100% | 0% |
| Normal event FPR | 1.4695% | 1.1680% |

DeepSeek 对合法分页返回 `benign`，置信度 0.95；13 个攻击候选全部保留。因此：

- Precision 增益：+7.14 个百分点；
- 分页事件 FPR 降低：100 个百分点；
- Episode Recall 损失：0；
- Target-event Recall 损失：0。

该消融证明 LLM 在“确定性证据相似、但可信业务契约能够解释行为”的候选上
具有过滤价值。它不意味着正式配置原本存在 100% 分页误报。

## 8. 调用与成本记录

Development 13 个攻击候选和分页消融 1 个候选共进行 14 次成功复核：

| 项目 | Tokens |
|---|---:|
| Prompt | 114,490 |
| Completion | 10,727 |
| Total | 125,217 |

14 次复核均在第一次合法输出尝试内完成，评测运行没有错误或拒答。模型响应、
缓存和评测输出保存在 Git 忽略的 `outputs/` 下。

## 9. 结论

1. 40 秒重叠解决了短 episode 落在窗口边界造成的漏检，development Episode
   Recall 达到 100%。
2. 正式配置在当前 pure-normal 数据上没有产生候选，分页 FPR 为 0。
3. 正式配置没有候选级 FP，因此 LLM 在该设置下没有可见 Precision 增益。
4. 在保留分页相似候选的消融中，DeepSeek 将 Precision 从 92.86% 提高到
   100%，同时保持 100% Recall。
5. 结果支持“确定性高 Recall 候选 + 可信正常上下文 + Skill 约束 LLM 复核”
   的设计，但尚不足以形成正式泛化结论。

## 10. 局限性与后续实验

- 数据来自合成本地靶场，不代表生产 API 流量；
- 40 秒重叠已使用 development 标签选择；
- pure-normal 普通事件来自同一次生成运行，独立性有限；
- 合法分页来自一个单一 fixture，场景多样性不足；
- 尚未测试批处理、稀疏资源 ID、网关重试、乱序、日志缺失和共享 IP 等困难
  正常行为；
- 尚未生成独立 validation 与 blind-test；
- 当前只评测参数遍历，不能推广到其他五类异常；
- DeepSeek 单模型、单次运行不足以评估模型方差和置信度校准。

后续应使用不同随机种子生成场景隔离的 validation 和 blind-test，冻结配置、
Prompt 与 Skill 后一次性评测，并至少重复模型调用三次以报告均值和方差。
