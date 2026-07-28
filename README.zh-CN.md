# SentinelFlow

简体中文 | [English](README.md)

SentinelFlow 是一个面向事件序列的可解释安全审计框架。系统先用确定性程序计算
窗口、参数分布和候选证据，再用受版本化 Security Skill 约束的 LLM 复核候选，
最后通过独立 evaluator 计算 Precision、Recall 和误报率。

当前 MVP 聚焦 API 请求日志中的参数遍历检测。架构已为越权、接口滥用、请求
重放、调用序列异常和参数异常等类别预留扩展位置。

## 工作流程

```text
API JSONL 日志
  → 规范化与事件窗口
  → 确定性参数特征
  → 高 Recall 候选检测
  → API Security Skill + DeepSeek 复核
  → 本地 Schema 与证据一致性校验
  → 告警和独立指标评测
```

系统坚持以下边界：

- 数量、比例、熵、时间间隔等精确计算由程序完成；
- LLM 只负责语义复核、正常替代解释和证据组织；
- 日志内容始终视为不可信数据；
- 模型输出必须通过本地 Schema、类别、证据值和请求序号校验；
- Ground Truth 只允许进入 evaluator，不得进入检测器、Prompt 或正常上下文；
- API Key 只从环境变量或本地 `.env` 读取，不进入 Git、日志或缓存键。

## 当前能力

- 流式读取和严格校验 UTF-8 JSONL；
- UTC 时间、HTTP 方法和路径规范化；
- 确定性、可重叠、按主体分组的事件窗口；
- 嵌套 Body 参数提取；
- 基数、熵、连续性、固定步长、响应分布、时间和上下文稳定性特征；
- 可配置的参数遍历高 Recall 候选检测；
- 重叠窗口候选稳定去重；
- 版本化 API Security Skill；
- DeepSeek OpenAI-compatible Chat Completions adapter；
- JSON Object 输出、超时、有限重试和安全错误记录；
- 基于完整 Prompt、Schema 和模型配置的 SHA-256 本地缓存；
- 候选级、episode 级和请求级独立 evaluator；
- DeepSeek 模型版本、Token、耗时、尝试次数和缓存命中记录。

## 安装

项目使用 [Pixi](https://pixi.sh/) 管理可复现环境：

```bash
pixi install
pixi run check
```

`pixi run check` 会依次运行 Ruff、格式检查、Pyright 和 Pytest。

## 配置 DeepSeek

```bash
cp .env.example .env
```

然后在 `.env` 中填写：

```dotenv
SENTINELFLOW_LLM_API_KEY=你的_DeepSeek_API_Key
```

默认配置为：

- 供应商：DeepSeek；
- 模型：`deepseek-v4-pro`；
- API：OpenAI-compatible Chat Completions；
- Base URL：`https://api.deepseek.com`；
- 输出：`json_object`；
- Thinking：关闭；
- Temperature：`0`；
- 缓存目录：`outputs/cache`。

`.env` 和 `outputs/` 均被 Git 忽略。

## CLI 使用

检查输入日志：

```bash
pixi run sentinelflow inspect \
  --input /path/to/api_requests.jsonl
```

查看单个参数的确定性窗口特征：

```bash
pixi run sentinelflow profile-parameter \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --window-seconds 60 \
  --overlap-seconds 40
```

生成候选：

```bash
pixi run sentinelflow detect-parameter-enumeration \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --config configs/parameter-enumeration.yaml \
  --output outputs/candidates.jsonl
```

使用 DeepSeek 复核：

```bash
pixi run sentinelflow review-parameter-enumeration \
  --input /path/to/api_requests.jsonl \
  --parameter body.posid \
  --config configs/parameter-enumeration.yaml \
  --env-file .env \
  --output outputs/reviews.jsonl
```

如果业务方具有可信的分页、批处理或重试契约，可以通过
`--normal-context context.json` 提供。该文件不能包含 Ground Truth 或隐藏标签。

独立评测：

```bash
pixi run sentinelflow evaluate-parameter-enumeration \
  --ground-truth /path/to/ground_truth.jsonl \
  --candidates outputs/candidates.jsonl \
  --reviews outputs/reviews.jsonl \
  --output outputs/evaluation-report.json
```

## 实验数据

2026-07-28 实验使用相邻 `ad-scout/api_security_lab` 生成器已有的一次完整运行：

- 随机种子：`20260726`；
- 虚拟客户端：12；
- API 请求：3000 条；
- 正常请求：2646 条；
- 参数遍历：106 条，组成 13 个连续 episode；
- 接口滥用：198 条；
- 越权：11 条；
- 调用序列异常：12 条；
- 请求重放：13 条；
- 参数异常：14 条。

API 日志和 Ground Truth 各 3000 行，请求 ID 与序号逐行完全对齐。纯正常集由
2646 条正常请求和 8 条合法分页请求组成，共 2654 条。具体哈希、拆分方式和
限制见 [数据 Manifest](datasets/ad-scout-20260726.manifest.json)。

## 实验结果

开发集调参仅调整了窗口重叠：

| 60 秒窗口重叠 | Episode Recall | 混合集候选误报 | 纯正常候选 |
|---:|---:|---:|---:|
| 10 秒 | 11/13（84.62%） | 0 | 0 |
| 40 秒 | 13/13（100%） | 0 | 0 |

正式配置 `1.1` 使用 40 秒重叠：

| 指标 | 结果 |
|---|---:|
| 参数遍历 episode Recall | 13/13（100%） |
| 参数遍历请求 Recall | 106/106（100%） |
| 候选级 Precision | 13/13（100%） |
| 纯正常集候选 | 0/2654 |
| 合法分页事件误报率 | 0/8（0%） |
| DeepSeek 攻击候选复核 | 13/13 `alert` |
| LLM 失败或拒答 | 0 |

正式配置已在候选阶段抑制声明的分页参数，因此这一设置下 LLM 的 Precision
增益为 0。为了单独测量 LLM 的作用，实验增加了一个只关闭分页预抑制的消融：

| 分页消融指标 | 仅候选 | 候选 + DeepSeek |
|---|---:|---:|
| 候选/告警数 | 14 | 13 |
| 真阳性 | 13 | 13 |
| 假阳性 | 1 | 0 |
| Precision | 92.86% | 100% |
| Episode Recall | 100% | 100% |
| 分页事件误报率 | 100% | 0% |

DeepSeek 将 13 个攻击候选全部保留为 `alert`，将合法分页候选判为 `benign`
（置信度 0.95），因此 Precision 提升 **7.14 个百分点**，且 Recall 没有下降。

14 次真实模型复核全部成功，API 共报告：

- Prompt Tokens：114,490；
- Completion Tokens：10,727；
- Total Tokens：125,217。

完整实验设计、口径、结果解释和局限性见
[中文实验报告](docs/experiment-results.zh-CN.md)。

## 结果边界

当前结果用于开发验证，不能视为正式盲测结论：

- 数据来自本地合成 API 靶场，不是生产流量；
- 窗口重叠参数已在 development 上选择；
- pure-normal 分区来自同一生成运行中的正常标签，分页来自仓库 fixture；
- 尚未使用独立 validation 和 blind-test 随机种子；
- 当前只完成 `parameter_enumeration` 类别的端到端闭环。

下一步应生成互不重叠的 validation/blind-test 运行，并扩充批处理、稀疏 ID、
重试、乱序和共享来源等困难正常场景。

## 项目结构

```text
sentinelflow/core          事件、读取、规范化、窗口
sentinelflow/features      确定性特征
sentinelflow/detectors     候选检测和去重
sentinelflow/llm           Provider adapter、Prompt、Skill、缓存和校验
sentinelflow/evaluation    独立指标评测
domains/api_security       API Security Skill 和领域资料
configs                    版本化运行配置
datasets                   Manifest 和数据说明
docs                       架构、计划和实验报告
tests                      自动化测试
```

## 文档

- [架构说明](docs/architecture.md)
- [MVP 实施计划](docs/mvp-implementation-plan.zh-CN.md)
- [实验结果报告](docs/experiment-results.zh-CN.md)
- [数据集说明](datasets/README.md)

## License

Apache License 2.0
