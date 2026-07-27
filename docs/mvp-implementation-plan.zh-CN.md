# SentinelFlow MVP 实现与技术任务清单

## 1. 文档目的

本文定义 SentinelFlow 第一个可交付版本的范围、技术架构、实现顺序、任务清单和验收标准。

MVP 只完成一个目标：

> 离线读取结构化 API 请求日志，结合确定性特征计算与大语言模型分析请求序列、参数分布和访问模式，识别安全异常，输出可解释告警，并使用独立 Ground Truth 计算检出率和误报率。

本阶段不追求实时流处理、自动处置、Web 控制台、多 Agent 协作或跨领域适配。先建立一条可运行、可复现、可评测的端到端链路。

---

## 2. MVP 范围

### 2.1 输入

输入为按时间排序的 JSONL 文件，每行表示一条 API 请求。第一版适配现有 `api_security_lab` 日志，至少支持以下字段：

| 字段 | 类型 | 用途 |
|---|---|---|
| `timestamp` | ISO 8601 字符串 | 计算时间间隔和访问频率 |
| `request_id` | 字符串 | 请求关联和重放检测 |
| `source_ip` | 字符串 | 来源聚合 |
| `actor` | 字符串 | 认证主体聚合 |
| `method` | 字符串 | 区分接口操作 |
| `path` | 字符串 | API 序列和访问模式 |
| `body` | JSON 对象 | 参数分布、资源 ID 和会话分析 |
| `http_status` | 整数 | 探测结果和响应模式 |
| `response_code` | 字符串 | 业务响应辅助证据 |
| `response_item_count` | 整数 | 批量请求影响 |
| `issued_sid` | 字符串 | 会话签发和使用关联 |
| `duration_ms` | 数字 | 辅助性能和异常分析 |

日志中不得包含 `is_anomaly`、`category`、攻击名称或其他答案字段。

### 2.2 输出

系统输出两个文件：

1. `alerts.jsonl`：安全告警，一行一个攻击事件；
2. `predictions.jsonl`：请求级预测，用于和 Ground Truth 对齐评测。

告警必须包含：

- 告警类别；
- 风险等级；
- 置信度；
- 涉及的请求序号；
- 主体、来源和时间范围；
- 可验证的关键证据；
- 对行为的简洁解释；
- 至少一个被排除或仍需关注的正常解释。

### 2.3 首批异常类别

MVP 固定支持以下六类：

| 类别 | 标识 | 核心判断 |
|---|---|---|
| 横向越权 | `horizontal_overreach` | 当前主体访问其他主体拥有的资源 |
| 调用序列异常 | `sequence_violation` | 缺少必要前序操作或使用无效会话 |
| 参数遍历 | `parameter_enumeration` | 短时间系统性尝试多个资源标识 |
| 接口滥用 | `api_abuse` | 相同主体、会话或参数的异常高频调用 |
| 请求重放 | `request_replay` | 合法请求后出现等价重复请求 |
| 参数异常 | `parameter_anomaly` | 参数显著偏离基线且存在语义不一致 |

### 2.4 明确不做

- 实时 Kafka/Flink 流处理；
- Web UI 和多租户管理；
- 自动封禁、限流或工单处置；
- 自主规划型多 Agent；
- 模型微调；
- 向量数据库和复杂 RAG；
- SQL、云审计、金融风控等其他领域；
- 生产级身份、权限和密钥管理；
- 对自然语言或非结构化访问日志的全面兼容。

---

## 3. 成功标准

### 3.1 功能标准

- 一条命令完成日志读取、分析和告警输出；
- 支持 3000 条现有靶场日志；
- 六类异常均能在输出中表达；
- 每条告警能定位到具体请求序号；
- 模型输出不合法时能够校验失败并重试或记录错误；
- 审计链路完全不能读取 Ground Truth；
- 一条独立命令完成指标评测。

### 3.2 指标标准

第一阶段建议目标，不作为最终论文结论：

- 请求级 Recall ≥ 0.80；
- 请求级 Precision ≥ 0.80；
- 请求级 FPR ≤ 0.05；
- 六个类别均至少检出一个完整场景；
- 所有正式告警均包含非空证据和解释；
- 相同输入、配置和模型参数可复现实验过程。

除总体指标外，必须报告：

- 每类别 Precision、Recall 和 F1；
- Macro F1；
- Micro F1；
- 场景级 Recall；
- 正常请求的 FPR；
- LLM 调用次数、Token 用量、耗时和估算成本。

不能只报告 Accuracy。当前正常样本占多数，Accuracy 容易掩盖漏报。

---

## 4. 核心技术决策

### 4.1 使用混合审计架构

MVP 不采用“把整份日志直接交给 LLM”的方案，而采用：

```text
JSONL 日志
  -> 解析和规范化
  -> 实体、会话和资源关联
  -> 滑动窗口与确定性特征
  -> 候选异常发现
  -> LLM 语义复核和解释
  -> 告警校验、去重和请求级映射
  -> Ground Truth 评测
```

分工原则：

- 程序负责精确计算：次数、间隔、重复哈希、基数、序列位置和归属映射；
- LLM 负责语义判断：业务合理性、异常分类、证据组织、正常替代解释和告警文本；
- Skill 负责固定判断方法、证据要求和误报控制；
- Evaluator 只在审计完成后读取 Ground Truth。

### 4.2 MVP 不是自主 Agent

第一版实现为可控的智能审计流水线，不让模型自由选择任意工具。这样更容易：

- 保证输入边界；
- 重现实验；
- 计算稳定指标；
- 比较不同模型和 Prompt；
- 控制 Token 成本；
- 定位误报与漏报原因。

后续可在稳定流水线基础上增加“扩大窗口、查询会话、查询资源归属”等调查工具，升级为 Agent。

### 4.3 离线批处理优先

离线批处理能够保留完整历史，适合建立第一版正确性基线。实时模式需要额外处理乱序、迟到事件、状态持久化和告警撤回，不属于 MVP。

---

## 5. 目录与模块设计

计划中的代码职责如下：

```text
sentinelflow/
  core/
    models.py          统一事件、窗口和上下文模型
    jsonl.py           JSONL 读取和写入
    normalize.py       字段规范化、时间解析和序号分配
    windowing.py       按实体构建时间窗口
    context.py         会话、资源和历史状态关联

  features/
    timing.py          间隔、速率和突发特征
    sequence.py        前序操作、状态转换和路径序列
    parameters.py      基数、变化趋势和分布偏离
    replay.py          请求指纹与重复关系
    ownership.py       actor、profile、session、resource 归属关系

  detectors/
    base.py            候选检测器协议
    authorization.py   越权候选
    sequence.py        序列异常候选
    enumeration.py     参数遍历候选
    abuse.py           高频滥用候选
    replay.py          重放候选
    parameters.py      参数异常候选

  llm/
    client.py          模型调用接口
    providers/         具体模型供应商适配
    prompts.py         Skill 与上下文装配
    schemas.py         结构化输出模型
    retry.py           超时、重试和错误分类
    cache.py           基于输入哈希的本地缓存

  alerts/
    models.py          告警和证据模型
    validate.py        输出校验
    merge.py           重叠窗口告警合并
    project.py         告警映射为请求级预测

  evaluation/
    align.py           预测与 Ground Truth 对齐
    metrics.py         请求级和类别级指标
    scenarios.py       场景级指标
    report.py          JSON 与 Markdown 报告

  cli/
    audit.py           `sentinelflow audit`
    evaluate.py        `sentinelflow evaluate`

domains/api_security/
  schemas/
    event.schema.json
    alert.schema.json
  rules/
    taxonomy.yaml
    ownership.yaml
    workflows.yaml
    thresholds.yaml
  skills/
    audit-api-security/
      SKILL.md
      references/
  examples/

configs/
  api-security.example.yaml
```

---

## 6. 数据模型

### 6.1 统一事件模型

内部事件不应直接依赖原始日志字典。建议建立不可变模型：

```python
AuditEvent(
    sequence_no: int,
    timestamp: datetime,
    request_id: str,
    actor: str,
    source_ip: str,
    method: str,
    path: str,
    body: dict,
    http_status: int | None,
    response_code: str | None,
    issued_sid: str | None,
)
```

规范化阶段需要：

- 自动补充 `sequence_no`；
- 把时间统一转换成带时区的 UTC `datetime`；
- 统一 HTTP 方法为大写；
- 统一路径格式并移除查询字符串；
- 保留原始记录和原始行号；
- 对缺少字段给出明确错误或默认值；
- 不在日志中保留模型密钥；
- 可选脱敏 Authorization、Cookie、手机号等字段。

### 6.2 窗口模型

窗口至少包含：

```python
EventWindow(
    window_id: str,
    entity_key: str,
    start_time: datetime,
    end_time: datetime,
    events: tuple[AuditEvent, ...],
    features: dict,
)
```

第一版建议同时构造：

- 全局顺序窗口：用于跨主体的背景；
- `actor` 窗口：用于权限和主体行为；
- `actor + source_ip` 窗口：用于遍历和滥用；
- `sid` 窗口：用于调用链和会话异常；
- `request_id` 分组：用于重放。

建议默认时间窗口 60 秒、重叠 10 秒。枚举和滥用检测器可以使用更短的内部时间范围，但不应通过切断上下文丢失前序事件。

### 6.3 候选异常模型

候选不是正式告警。候选对象应包含：

```json
{
  "candidate_id": "candidate-0001",
  "suggested_category": "parameter_enumeration",
  "sequence_numbers": [421, 422, 423, 424],
  "entity": {
    "actor": "media-client-a",
    "source_ip": "10.42.20.10"
  },
  "features": {
    "duration_seconds": 0.71,
    "distinct_posids": 6,
    "consecutive_ratio": 1.0,
    "status_counts": {"200": 2, "404": 4}
  },
  "raw_events": []
}
```

候选发现阶段以高 Recall 为目标，允许一定冗余；LLM 复核和告警合并负责降低误报。

### 6.4 告警模型

建议告警 Schema：

```json
{
  "alert_id": "alert-0001",
  "category": "parameter_enumeration",
  "severity": "high",
  "confidence": 0.94,
  "actor": "media-client-a",
  "source_ip": "10.42.20.10",
  "start_sequence": 421,
  "end_sequence": 426,
  "sequence_numbers": [421, 422, 423, 424, 425, 426],
  "evidence": [
    {
      "type": "parameter_pattern",
      "observation": "0.71 秒内尝试 6 个连续递增的 posid",
      "sequence_numbers": [421, 422, 423, 424, 425, 426]
    }
  ],
  "explanation": "该来源短时间系统性探测相邻广告位，响应混合出现成功和不存在，符合参数遍历。",
  "benign_alternative": "单次配置错误不能解释连续递增的多个广告位尝试。",
  "model": {
    "provider": "configured-provider",
    "name": "configured-model",
    "skill_version": "0.1.0"
  }
}
```

模型不得自由创造类别。所有字段必须通过本地 Schema 校验。

---

## 7. 六类异常的第一版检测方案

### 7.1 横向越权

需要建立资源归属表：

```text
profile_id -> owner actor
sid        -> issuing actor + profile_id
view_id    -> actor + sid + posid
```

候选规则：

- 当前 `actor` 与目标 `profile_id` 的 owner 不一致；
- 当前 `actor` 使用其他 actor 签发的 `sid`；
- 当前 actor 操作其他主体生成的 `view_id`。

LLM 复核重点：

- 是否存在共享、委托或管理员权限；
- 资源归属是否来自可信配置；
- HTTP 200 不代表授权合法。

最低证据：

- 当前认证主体；
- 目标资源；
- 已知资源 owner；
- 发生冲突的请求序号。

### 7.2 调用序列异常

先定义最小业务状态机：

```text
profile -> mediation -> launch(sid) -> mview(view_id)
        -> win_notice -> exposure
```

候选规则：

- `mview` 使用空、未知或归属不一致的 `sid`；
- 使用 `view_id` 前没有对应成功的 `mview`；
- 曝光发生在广告拉取或竞价通知之前。

误报控制：

- 窗口截断时向前查询完整历史；
- 区分日志丢失和真正缺少前序；
- 允许配置中声明可选步骤。

### 7.3 参数遍历

按 `actor + source_ip + path + 参数名` 聚合。

确定性特征：

- 窗口内请求数量；
- 不同参数值数量；
- 数字范围跨度；
- 相邻递增/递减比例；
- 参数熵；
- HTTP 200/404 分布；
- 相同会话和其他参数的稳定程度；
- 首末请求时间差。

第一版候选阈值可配置，例如：

```text
60 秒内 distinct(posid) >= 5
并且 consecutive_ratio >= 0.6
或 invalid_ratio >= 0.5
```

不能仅凭单个 404、单个不同 ID 或正常分页判为遍历。

### 7.4 接口滥用

按 `actor + source_ip + path` 聚合，并可进一步比较 `sid + posid`。

确定性特征：

- 每秒/每分钟请求数；
- 平均、P50、P95 间隔；
- 最长连续突发；
- 相同请求参数比例；
- 相同会话比例；
- 成功率和返回数量；
- 相对正常基线的倍数。

第一版可以使用靶场正常数据建立静态基线。告警条件应同时满足：

- 请求频率显著偏离基线；
- 请求高度重复或缺少业务性变化；
- 行为不能用少量网络重试解释。

### 7.5 请求重放

构造规范化请求指纹：

```text
hash(actor, method, path, canonical_body)
```

`canonical_body` 应：

- JSON key 排序；
- 排除明确的瞬时字段时需由配置声明；
- 保留与幂等性和业务动作相关字段；
- 不依赖字典原始顺序。

候选规则：

- 相同 `request_id` 重复；
- 或相同指纹在极短时间重复；
- 第一条作为基准，后续等价请求为疑似重放。

误报控制：

- 检查接口是否幂等；
- 检查 SDK 或网关重试标记；
- 检查第一次请求是否超时或失败；
- 只有重复发生的请求映射为异常。

### 7.6 参数异常

从可信正常数据建立：

- 数值参数分位数；
- 类别参数合法集合；
- 参数共现关系；
- `actor/profile/app/package/sdk/device` 语义关系。

候选规则：

- 数值明显超出正常范围；
- 罕见值与其他参数同时矛盾；
- 单次请求造成异常放大效果，例如大量返回对象。

单个罕见值不足以形成高置信告警。第一版至少要求“分布异常 + 语义不一致”中的两个证据。

---

## 8. LLM 与 Skill 设计

### 8.1 LLM 的输入

每次模型调用只包含：

- 系统级安全审计约束；
- API Security Skill；
- 当前候选类别；
- 相关原始事件；
- 代码计算出的确定性特征；
- 必要的资源归属和正常流程；
- 输出 JSON Schema。

不得包含：

- Ground Truth；
- 异常流量生成器；
- 数据集类别统计答案；
- 其他实验的正确输出；
- API Key 或未脱敏凭据。

### 8.2 LLM 的任务

要求模型只完成：

1. 判断候选是否构成安全异常；
2. 在固定 taxonomy 中选择类别；
3. 选择涉及的请求序号；
4. 引用输入中可验证的证据；
5. 给出简洁解释；
6. 分析一个合理的正常替代解释；
7. 输出置信度。

模型不负责精确计算请求频率或重新解析全部日志。

### 8.3 Skill 的内容

`SKILL.md` 后续需要逐步加入：

- 分析工作流；
- 六类异常定义；
- 每类最低证据；
- 误报控制；
- 置信度标定；
- 告警聚合原则；
- 信息不足时的 abstain 规则；
- 输出要求。

详细 taxonomy、正常流程和字段说明放在 `references/`，避免主 Skill 过长。

### 8.4 稳定性配置

MVP 建议：

- temperature 设为 0 或供应商允许的最低值；
- 使用结构化输出或 JSON Schema；
- 对 Schema 错误最多重试两次；
- 模型调用设置超时；
- 使用输入哈希缓存成功响应；
- 保存模型名、Skill 版本、Prompt 版本和调用时间；
- 不保存密钥；
- 失败候选写入单独错误文件，不静默丢弃。

---

## 9. 评测设计

### 9.1 严格隔离

审计命令和评测命令必须是两个独立入口：

```bash
pixi run audit --input api_requests.jsonl --output outputs/run-001
pixi run evaluate \
  --predictions outputs/run-001/predictions.jsonl \
  --ground-truth ground_truth.jsonl
```

`audit` 的配置对象中不应存在 Ground Truth 路径。测试应明确验证审计模块不能导入 evaluator 的答案读取逻辑。

### 9.2 请求级指标

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
FPR       = FP / (FP + TN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

另外报告：

```text
告警误报占比 = FP / (TP + FP) = 1 - Precision
```

文档和报告必须区分 FPR 与告警误报占比。

### 9.3 场景级指标

遍历和滥用是多请求场景，不能只依赖请求级逐行匹配。建议定义：

- 预测告警与真实场景的请求集合存在交集；
- 类别一致；
- 交并比达到可配置阈值，或命中场景中最少请求数；
- 同一真实场景只计一次检出；
- 多个重复告警额外计入重复告警率。

### 9.4 数据拆分

至少生成：

- 开发集：调整特征和 Prompt；
- 验证集：选择阈值；
- 盲测集：最终评测；
- 纯正常集：专门测 FPR。

拆分必须使用不同随机种子。不得在盲测结果上反复调参。

### 9.5 对照实验

最终至少比较三种方案：

1. 纯确定性规则；
2. 纯 LLM 窗口分析；
3. 候选检测 + LLM 复核的混合方案。

比较指标：

- 检出率；
- 误报率；
- F1；
- 每类表现；
- 解释完整度；
- 推理成本；
- 运行时间。

---

## 10. 配置设计

`configs/api-security.example.yaml` 建议包含：

```yaml
input:
  format: jsonl
  timezone: UTC

window:
  seconds: 60
  overlap_seconds: 10
  entity_keys:
    - actor
    - source_ip

detectors:
  parameter_enumeration:
    minimum_distinct_values: 5
    minimum_consecutive_ratio: 0.6
  api_abuse:
    minimum_requests: 10
    maximum_duration_seconds: 2
  request_replay:
    maximum_interval_seconds: 1

llm:
  provider: null
  model: null
  temperature: 0
  timeout_seconds: 60
  maximum_retries: 2
  cache_directory: outputs/cache

alerts:
  minimum_confidence: 0.70

privacy:
  redact_headers:
    - authorization
    - cookie
```

密钥只通过环境变量读取，例如 `SENTINELFLOW_LLM_API_KEY`，不得写入 YAML、日志、缓存或 Git。

---

## 11. CLI 设计

### 11.1 审计

```bash
sentinelflow audit \
  --config configs/api-security.example.yaml \
  --input datasets/dev/api_requests.jsonl \
  --output outputs/dev-run-001
```

输出目录：

```text
outputs/dev-run-001/
  manifest.json
  candidates.jsonl
  alerts.jsonl
  predictions.jsonl
  errors.jsonl
  usage.json
```

### 11.2 评测

```bash
sentinelflow evaluate \
  --ground-truth datasets/dev/ground_truth.jsonl \
  --predictions outputs/dev-run-001/predictions.jsonl \
  --alerts outputs/dev-run-001/alerts.jsonl \
  --output outputs/dev-run-001/evaluation
```

评测输出：

```text
evaluation/
  metrics.json
  report.md
  confusion-by-category.csv
  false-positives.jsonl
  false-negatives.jsonl
```

---

## 12. 分阶段任务清单

任务按依赖关系排序。每个阶段完成后再进入下一阶段。

### 阶段 0：冻结实验边界

- [ ] 明确 MVP 只支持离线 JSONL API 日志；
- [ ] 冻结六类异常 taxonomy 和名称；
- [ ] 明确请求级和场景级标注语义；
- [ ] 从原项目复制或生成开发、验证、盲测、纯正常数据；
- [ ] 为每份数据记录生成参数、随机种子和 SHA-256；
- [ ] 确保 Ground Truth 与审计输入物理隔离；
- [ ] 在 `datasets/README.md` 记录数据使用边界。

验收标准：

- 四类数据集有独立 manifest；
- API 日志不包含标签；
- 相同行号、请求字段与 Ground Truth 能正确对齐；
- 盲测 Ground Truth 不用于开发。

### 阶段 1：项目打包和基础契约

- [ ] 确定 `src` layout 或当前 package layout；
- [ ] 增加 Python 项目元数据和 CLI entry points；
- [ ] 定义 `AuditEvent`、`EventWindow`、`Candidate`、`Alert`；
- [ ] 编写 API 事件 JSON Schema；
- [ ] 编写告警 JSON Schema；
- [ ] 编写示例配置文件；
- [ ] 建立统一异常类型和错误类型；
- [ ] 增加单元测试和 fixture 目录。

验收标准：

- Pixi 可以安装并执行全部任务；
- 示例事件和告警通过 Schema 校验；
- 非法时间、缺失字段和非法置信度有确定错误；
- `pixi run check` 通过。

### 阶段 2：日志读取与规范化

- [ ] 实现流式 JSONL reader，避免一次性加载大文件；
- [ ] 自动分配并保留原始行号；
- [ ] 解析 ISO 8601 时间和时区；
- [ ] 规范化方法、路径和空字段；
- [ ] 实现请求体安全截断策略；
- [ ] 实现敏感字段脱敏；
- [ ] 校验输入按时间排序，或提供显式排序选项；
- [ ] 输出规范化统计摘要。

验收标准：

- 3000 条靶场日志完整读入；
- 不丢行、不重复；
- 错误行包含文件名和行号；
- 原始 `sequence_no` 可追溯；
- 敏感字段不会进入模型上下文。

### 阶段 3：上下文与窗口

- [ ] 建立 actor、source、sid、profile、view 关系索引；
- [ ] 实现固定时间滑动窗口；
- [ ] 支持按 actor 和 actor+source 聚合；
- [ ] 为序列检测支持向前历史查询；
- [ ] 为重叠窗口生成稳定 `window_id`；
- [ ] 编写窗口边界和跨窗口测试；
- [ ] 输出窗口级调试摘要。

验收标准：

- 枚举和突发片段不会因窗口边界完全丢失；
- 同一事件可以出现在重叠窗口，但最终可去重；
- 会话签发记录可关联到后续请求。

### 阶段 4：确定性特征

- [ ] 实现请求速率和间隔统计；
- [ ] 实现请求规范化指纹；
- [ ] 实现参数路径提取，如 `body.posid`；
- [ ] 实现不同值数量、范围、相邻比例和熵；
- [ ] 实现参数共现和基线分布；
- [ ] 实现业务状态机特征；
- [ ] 实现资源归属冲突特征；
- [ ] 为每个特征编写边界测试。

验收标准：

- 给定固定输入，特征结果完全确定；
- 数值和时间计算不依赖 LLM；
- 每个特征都能追溯到原始请求序号。

### 阶段 5：候选检测器

- [ ] 定义统一 Detector 协议；
- [ ] 实现横向越权候选检测器；
- [ ] 实现序列异常候选检测器；
- [ ] 实现参数遍历候选检测器；
- [ ] 实现接口滥用候选检测器；
- [ ] 实现请求重放候选检测器；
- [ ] 实现参数异常候选检测器；
- [ ] 将所有阈值移入配置；
- [ ] 实现候选去重；
- [ ] 记录每个候选的确定性证据。

验收标准：

- 在开发集上每类真实异常至少产生一个候选；
- 候选阶段优先保证 Recall；
- 候选中不包含 Ground Truth 字段；
- 每个候选包含非空请求序号和特征。

### 阶段 6：安全 Skill

- [ ] 完成 `SKILL.md` 工作流；
- [ ] 写明六类异常的最低证据；
- [ ] 写明每类常见正常解释；
- [ ] 定义置信度区间；
- [ ] 定义信息不足时不告警；
- [ ] 定义多请求场景的合并原则；
- [ ] 将详细 taxonomy 放入 references；
- [ ] 使用 Skill 校验脚本验证结构；
- [ ] 用不含答案的样例进行人工审阅。

验收标准：

- Skill 不引用 Ground Truth；
- 不把单个 404 判定为遍历；
- 不把所有高频行为判定为滥用；
- 所有告警要求引用具体请求证据。

### 阶段 7：LLM 接入

- [ ] 定义与供应商无关的 LLM Client 协议；
- [ ] 先实现一个模型供应商；
- [ ] 从环境变量读取密钥；
- [ ] 实现结构化输出；
- [ ] 实现 Schema 校验；
- [ ] 实现超时、重试和错误记录；
- [ ] 实现输入哈希缓存；
- [ ] 记录 Token、耗时和模型版本；
- [ ] 编写 Mock LLM 测试；
- [ ] 确保日志和异常信息不会泄露密钥。

验收标准：

- Mock 模型可以跑通全部流水线；
- 真实模型可以处理一个候选并生成合法告警；
- 非法 JSON 能够重试；
- 重复运行可命中缓存；
- 单个模型失败不会破坏其他候选结果。

### 阶段 8：告警处理

- [ ] 实现置信度阈值；
- [ ] 校验类别、证据和请求序号；
- [ ] 合并重叠窗口中的重复告警；
- [ ] 区分场景级告警和请求级预测；
- [ ] 实现严重度映射；
- [ ] 生成稳定 `alert_id`；
- [ ] 输出 `alerts.jsonl` 和 `predictions.jsonl`；
- [ ] 记录被模型否决的候选。

验收标准：

- 同一遍历片段不会产生大量重复告警；
- 告警请求序号全部存在于输入；
- 重放只把重复请求映射为异常；
- 输出可以被 evaluator 无歧义读取。

### 阶段 9：评测器

- [ ] 校验 Ground Truth 与预测对齐；
- [ ] 计算 TP、FP、TN、FN；
- [ ] 计算 Precision、Recall、FPR、F1 和 Accuracy；
- [ ] 计算每类别指标；
- [ ] 计算 Macro 和 Micro 指标；
- [ ] 实现场景级匹配；
- [ ] 计算重复告警率；
- [ ] 导出误报和漏报明细；
- [ ] 输出 JSON、CSV 和 Markdown 报告；
- [ ] 编写手工小样本验证公式。

验收标准：

- 已知混淆矩阵得到正确指标；
- 对缺失预测的处理规则固定并有测试；
- 重复 `request_id` 不会导致错误对齐；
- 报告明确区分 FPR 与 `1 - Precision`。

### 阶段 10：端到端 CLI

- [ ] 实现 `audit` 命令；
- [ ] 实现 `evaluate` 命令；
- [ ] 实现 `inspect` 或 `validate-data` 命令；
- [ ] 生成运行 manifest；
- [ ] 统一日志级别和退出码；
- [ ] 支持 `--dry-run` 查看窗口和候选数量；
- [ ] 在 README 中写最小运行示例。

验收标准：

- 从干净环境执行三条命令即可安装、审计和评测；
- 命令失败时返回非零退出码；
- 输出目录包含完整运行元数据；
- 同配置重复运行结果可追踪。

### 阶段 11：实验与调优

- [ ] 在开发集调整候选阈值和 Skill；
- [ ] 在验证集选择最终配置；
- [ ] 固定配置和版本；
- [ ] 运行纯规则基线；
- [ ] 运行纯 LLM 基线；
- [ ] 运行混合方案；
- [ ] 在纯正常集测 FPR；
- [ ] 最后运行一次盲测；
- [ ] 分析每类误报和漏报；
- [ ] 记录模型、Prompt、Skill、配置和数据版本。

验收标准：

- 实验可由 manifest 重放；
- 三种方案结果可比较；
- 盲测结果没有用于回调参数；
- 最终报告包含局限性而非只展示最佳数字。

### 阶段 12：文档和演示

- [ ] 完善项目 README；
- [ ] 编写架构设计文档；
- [ ] 编写数据格式和隐私说明；
- [ ] 编写 Skill 设计说明；
- [ ] 编写指标定义；
- [ ] 准备一段正常流量和一段攻击流量演示；
- [ ] 展示告警证据和正常替代解释；
- [ ] 整理实验表格和结论；
- [ ] 写明已知局限和后续扩展。

验收标准：

- 新开发者可根据 README 完成一次运行；
- 告警可以被人工追溯到原始日志；
- 技术报告能清楚解释 LLM 的必要性及其边界。

---

## 13. 推荐实施顺序

按最小闭环推进，而不是先实现所有模块：

### 里程碑 A：无 LLM 的可评测基线

完成阶段 0–5 和阶段 9 的请求级部分。

交付：

- 能读取日志；
- 能产生六类候选；
- 能输出请求级预测；
- 能计算基础指标。

这是后续判断 LLM 是否真正带来提升的基线。

### 里程碑 B：单类 LLM 闭环

只选择 `parameter_enumeration`：

- 候选检测；
- Skill 规则；
- LLM 复核；
- 告警输出；
- 指标评测。

先把一个类别完整跑通，再复制模式到其他类别。

### 里程碑 C：六类完整 MVP

扩展到全部类别，完成去重、场景评测和 CLI。

### 里程碑 D：严格实验

完成多数据集、三种方案对照、成本统计和盲测。

---

## 14. 第一个开发迭代建议

下一次编码只做以下任务：

1. 增加项目 Python 打包元数据和 CLI 占位；
2. 定义 `AuditEvent`；
3. 实现 JSONL reader；
4. 实现时间与路径规范化；
5. 读取现有 3000 条日志并输出摘要；
6. 为正常、非法 JSON、缺字段和时区编写测试。

第一个迭代的完成命令目标：

```bash
pixi run sentinelflow inspect \
  --input /path/to/api_requests.jsonl
```

预期输出：

```text
events: 3000
actors: 2
sources: 12
time range: ...
paths: 9
status codes: ...
invalid rows: 0
```

这一迭代不接入 LLM，也不实现异常判断。先保证数据入口稳定可靠。

---

## 15. 主要风险与控制

| 风险 | 影响 | 控制措施 |
|---|---|---|
| Ground Truth 泄漏 | 指标失真 | 审计与评测分离，目录和接口隔离 |
| 类别不平衡 | 总体指标虚高 | 报告每类和 Macro 指标 |
| 窗口切断攻击 | 漏报 | 重叠窗口和历史查询 |
| LLM 不稳定 | 结果不可复现 | 低温度、Schema、缓存、版本记录 |
| LLM 计算错误 | 误报或漏报 | 所有统计由代码计算 |
| 合法重试被判攻击 | 误报 | idempotency、响应和重试上下文 |
| 合成数据过于简单 | 泛化差 | 多种子、纯正常集和困难样本 |
| 日志含敏感信息 | 数据泄漏 | 字段白名单和脱敏 |
| Token 成本过高 | 无法扩展 | 候选预筛、窗口压缩和缓存 |
| 告警重复 | 可用性差 | 场景级合并和稳定指纹 |

---

## 16. MVP 完成定义

只有同时满足以下条件，才认为 MVP 完成：

- [ ] Pixi 干净环境可安装并运行；
- [ ] 3000 条日志端到端处理成功；
- [ ] 六类检测器、Skill 和 LLM 复核可运行；
- [ ] 输出结构化、可验证、可去重的告警；
- [ ] 告警包含具体请求、测量证据和解释；
- [ ] 审计路径无法读取 Ground Truth；
- [ ] 请求级、类别级和场景级评测完成；
- [ ] 纯规则、纯 LLM、混合方案完成对照；
- [ ] 纯正常数据的误报率已测量；
- [ ] 实验配置、数据、Skill、Prompt 和模型均版本化；
- [ ] README 中的命令可由新环境复现；
- [ ] 最终技术报告记录指标、成本、局限和后续工作。

