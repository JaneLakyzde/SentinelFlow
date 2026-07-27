# SentinelFlow 相关研究与参考文献

## 1. 文档说明

本文整理与 SentinelFlow 相关的研究工作，重点覆盖：

1. 大语言模型与日志异常检测；
2. API 请求、调用序列和访问行为异常检测；
3. 大语言模型在网络安全领域中的应用；
4. 日志异常检测的传统方法、评测方法与数据集风险；
5. 上述工作对 SentinelFlow 技术设计和实验方案的启示。

本文当前属于聚焦型文献调研，不构成完整的系统性文献综述。正式论文如需宣称研究创新性，还应进一步执行可复现的数据库检索、去重、全文筛选和前向/后向引文追踪。

最后检索日期：2026-07-27。

---

## 2. 检索范围与策略

### 2.1 数据源

本轮主要检索以下一手来源：

- ACM Digital Library；
- IEEE Xplore 及 IEEE 论文元数据；
- USENIX；
- IJCAI；
- ICSE、ASE、FSE 等软件工程会议；
- arXiv；
- 作者或研究项目主页。

优先采用论文原文、正式会议页面、DOI 页面和作者主页。博客、厂商白皮书和二手聚合页面不作为核心学术证据。

### 2.2 关键词组

检索词主要包括：

```text
large language model log anomaly detection
LLM log anomaly detection
ChatGPT log anomaly detection
interpretable log analysis LLM
API anomaly detection request sequence
web API anomaly detection
API abuse detection machine learning
API invariant anomaly detection
LLM cybersecurity incident response
LLM security operations center
LLM vulnerability management
log anomaly detection benchmark data leakage
```

### 2.3 纳入标准

- 直接研究日志、事件序列、API 调用或安全事件；
- 研究异常检测、行为建模、告警解释或事件调查；
- 研究 LLM 在安全分析、日志分析或安全运营中的作用；
- 对 SentinelFlow 的检测架构、Skill、评测或解释设计有直接参考价值；
- 正式发表论文优先，重要预印本明确标注。

### 2.4 排除和降级标准

- 只研究 LLM 自身安全，但与安全日志分析没有直接联系；
- 仅介绍商业产品而没有可复现实验；
- 将 “API call” 仅作为操作系统恶意软件行为特征，且无法迁移到 HTTP API；
- 缺少方法、数据或实验说明的低质量来源；
- 无法确认论文身份或存在明显元数据冲突的来源。

### 2.5 术语歧义

文献中的 “API call anomaly detection” 经常指操作系统 API 或系统调用序列，而 SentinelFlow 关注的是 HTTP/Web API 请求。因此不能把所有 API Call 论文直接视为 Web API 安全研究。

操作系统 API 序列研究可用于参考序列表示方法，但越权、会话归属、参数遍历和业务接口滥用仍需 Web API 专用数据模型。

---

## 3. 最重要的直接相关工作

### 3.1 MINES：基于 Web API 不变量的可解释异常检测

**Zhang, W., Lin, Y., Kwok, C. F. A., Teoh, X., Xie, X., Liauw, F., Zhang, H., & Dong, J. S. (2026). _MINES: Explainable Anomaly Detection through Web API Invariant Inference_. ICSE 2026.**

- 论文：[arXiv:2512.06906](https://arxiv.org/abs/2512.06906)
- DOI：[10.1145/3744916.3773160](https://doi.org/10.1145/3744916.3773160)
- 项目页：[MINES](https://sites.google.com/view/mines-anomaly-detection/home)
- 状态：ICSE 2026 正式接收。

#### 核心方法

MINES 不直接从原始日志实例学习黑盒分类器，而是：

1. 将 API Signature 转换成实体和表结构；
2. 结合数据库 Schema 与会话环境构造关系；
3. 使用 LLM 从结构信息中生成候选不变量；
4. 使用正常日志接受或淘汰候选不变量；
5. 将保留的不变量转换成可执行 Python 检查代码；
6. 在运行时根据不变量违反情况产生告警。

论文在 Train-Ticket、NiceFish、Gitea、Mastodon 和 NextCloud 上进行了评估，重点检测 Web 篡改和非法业务行为。

#### 与 SentinelFlow 的关系

这是目前与 SentinelFlow 最接近的论文：

- 都强调 API 之间以及 API 与业务状态之间的关系；
- 都强调 LLM 不能单独决定异常，需要确定性验证；
- 都追求可解释告警和低误报；
- 都适合将 LLM 用于生成或复核安全知识；
- 正常日志可以用于过滤 LLM 生成的错误规则。

主要区别：

- MINES 偏重 API、数据库和环境关系；
- SentinelFlow 偏重认证主体、会话、请求序列、参数分布和访问频率；
- MINES 的 LLM 主要用于离线不变量生成；
- SentinelFlow 计划让 LLM 进一步参与候选复核、攻击分类和解释生成。

#### 可借鉴设计

- Schema 级上下文优于无差别输入大量原始日志；
- LLM 生成的规则必须经过正常数据验证；
- 将最终检测逻辑编译成确定性代码；
- 使用不变量违反作为告警解释；
- 将规则生成成本和运行时检测成本分离。

---

### 3.2 WebNorm：以一致性正常性检测 Web 篡改异常

**Liao, Y., Xu, M., Lin, Y., Teoh, X., Xie, X., Feng, R., Liauw, F., Zhang, H., & Dong, J. S. (2024). _Detecting and Explaining Anomalies Caused by Web Tamper Attacks via Building Consistency-based Normality_. ASE 2024.**

- 会议页面：[ASE 2024](https://conf.researchr.org/details/ase-2024/ase-2024-research/43/Detecting-and-Explaining-Anomalies-Caused-by-Web-Tamper-Attacks-via-Building-Consiste)
- DOI：[10.1145/3691620.3695024](https://doi.org/10.1145/3691620.3695024)
- 预印本：[PDF](https://jasonbourne1998.github.io/data/ASE24.pdf)
- 状态：ASE 2024 正式论文。

#### 核心方法

WebNorm 从正常 Web 应用行为中提取三类正常性：

- 数据正常性：不同事件之间哪些信息必须保持一致；
- 流程正常性：特定条件下必须出现哪些事件；
- 常识正常性：参数应处于什么范围。

这些正常性被表示为一阶逻辑规则并转换为可执行检查。违反不变量既构成告警，也构成告警解释。

#### 与 SentinelFlow 的关系

WebNorm 的三类正常性可以直接映射到 SentinelFlow：

| WebNorm | SentinelFlow |
|---|---|
| 数据一致性 | actor、profile、sid、view_id 的归属关系 |
| 流程一致性 | launch、mview、win_notice、exposure 调用顺序 |
| 常识性范围 | count、频率、参数集合和参数共现关系 |

这篇论文为 SentinelFlow 的“正常行为基线 + 违反证据”设计提供了重要依据。

---

### 3.3 LogPrompt：基于 Prompt 策略的可解释在线日志分析

**Liu, Y., Tao, S., Meng, W., Wang, J., Ma, W., Zhao, Y., Chen, Y., Yang, H., Jiang, Y., & Chen, X. (2023). _Interpretable Online Log Analysis Using Large Language Models with Prompt Strategies_.**

- 论文：[arXiv:2308.07610](https://arxiv.org/abs/2308.07610)
- 代码：[LogPrompt](https://github.com/lunyiliu/LogPrompt)
- 状态：检索时以 arXiv 版本为主要依据。

#### 核心方法

LogPrompt 使用针对日志任务设计的 Prompt 策略进行日志解析和异常检测，包括：

- Self-prompt；
- Chain-of-Thought Prompt；
- In-context Prompt。

该工作强调在缺少域内训练数据时使用 LLM 的迁移能力，并通过专家评价考察解释的可读性和实用性。

#### 与 SentinelFlow 的关系

- 支持将 Security Skill 作为稳定的领域 Prompt；
- 支持构建纯 LLM 对照实验；
- 提醒不能只使用简单、无结构 Prompt；
- 解释质量应当单独评估，而不是只计算分类指标；
- 新域和未见日志是 LLM 相对传统监督模型的重要潜在优势。

#### 局限

- 主要处理通用系统日志；
- 不直接建模 HTTP API 的资源归属、权限和业务会话；
- LLM 仍不适合自行完成精确频率和时间间隔计算。

---

### 3.4 LogGPT：使用 ChatGPT 进行日志异常检测

**Qi, J., Huang, S., Luan, Z., Fung, C., Yang, H., & Qian, D. (2023). _LogGPT: Exploring ChatGPT for Log-Based Anomaly Detection_. HPCC 2023.**

- 论文：[arXiv:2309.01189](https://arxiv.org/abs/2309.01189)
- 状态：HPCC 2023；arXiv 页面提供公开版本。

#### 核心方法

该工作探索 ChatGPT 在 BGL 和 Spirit 数据集上的日志异常检测能力，并将其与传统深度学习方法比较。研究重点包括迁移能力、Prompt-based 分类和可解释性。

#### 与 SentinelFlow 的关系

- 可作为纯 LLM 基线；
- 可参考 Zero-shot 与 Few-shot 设计；
- 可比较无 Skill、简单 Prompt 和安全 Skill 三种设置；
- 可借鉴对解释结果的分析方式。

#### 注意：存在同名论文

另一篇论文也名为 LogGPT：

**Han, X., Yuan, S., & Trabelsi, M. (2023). _LogGPT: Log Anomaly Detection via GPT_.**

- 论文：[arXiv:2309.14482](https://arxiv.org/abs/2309.14482)

该工作训练 GPT 预测下一日志事件，并使用强化学习使训练目标更适合异常检测。它不是直接调用 ChatGPT 的 Prompt-based 审计器，引用时必须加以区分。

---

### 3.5 LogLLM：BERT 语义表示与 Llama 序列分类

**Guan, W., Cao, J., Qian, S., Gao, J., & Ouyang, C. (2024/2025). _LogLLM: Log-based Anomaly Detection Using Large Language Models_.**

- 论文：[arXiv:2411.08561](https://arxiv.org/abs/2411.08561)
- 状态：当前整理以 arXiv v5 为依据。

#### 核心方法

LogLLM：

1. 使用 BERT 提取日志消息语义向量；
2. 使用 Projector 对齐 BERT 和 Llama 的表示空间；
3. 使用 Llama 对日志序列进行分类；
4. 使用三阶段训练提高适应能力；
5. 尽量避免依赖传统日志模板解析。

#### 与 SentinelFlow 的关系

- 证明低层语义编码与高层序列判断可以分离；
- 可作为未来本地模型或微调研究方向；
- 可支持对不稳定日志格式的适配；
- 不适合作为 SentinelFlow MVP，因为训练和部署成本较高。

---

### 3.6 Retrieval-Augmented LLMs for Security Incident Analysis

**Cadet, X., Singh, A. V., Mamania, H., Koh, E., Fitts, A., Van Bruggen, D., Boboila, S., Chin, P., & Oprea, A. (2026). _Retrieval-Augmented LLMs for Security Incident Analysis_.**

- 论文：[arXiv:2603.18196](https://arxiv.org/abs/2603.18196)
- 状态：2026 年预印本。

#### 核心方法

该系统使用带 MITRE ATT&CK 技术标签的查询库，从多种日志中提取相关证据，再通过 RAG 和 LLM：

- 回答事件调查问题；
- 重建攻击序列；
- 提取恶意基础设施；
- 比较不同 LLM 的准确率、成本和性能。

#### 与 SentinelFlow 的关系

该论文非常支持 SentinelFlow 的混合架构：

```text
确定性查询和候选筛选
  -> 只提取相关上下文
  -> LLM 进行语义分析
```

SentinelFlow 初期不必引入向量数据库，可以先使用：

- actor；
- source_ip；
- sid；
- profile_id；
- request_id；
- 时间窗口；
- API path；

完成确定性上下文检索。

---

### 3.7 LLM 在安全事件响应中的协作价值与风险

**Kramer, D., Rosique, L., Narotam, A., Bursztein, E., Kelley, P. G., Thomas, K., & Woodruff, A. (2025). _Integrating Large Language Models into Security Incident Response_. SOUPS 2025.**

- 论文页：[USENIX SOUPS 2025](https://www.usenix.org/conference/soups2025/presentation/kramer)
- 状态：SOUPS 2025 正式论文。

#### 核心发现

研究使用 18 名安全分析师和 50 个真实安全事件，评估 LLM 生成安全事件总结的能力。论文显示：

- LLM 独立工作时可能遗漏关键事实；
- LLM 可能在总结中加入不准确内容；
- 人机协作能够降低分析师工作量；
- LLM 有助于改善报告可读性和一致性。

#### 与 SentinelFlow 的关系

这篇论文为以下设计提供负面证据和风险依据：

- 不让 LLM 独自读取整份日志并决定全部结果；
- 所有统计数字由程序计算；
- 告警必须引用具体请求；
- 输出必须经过 JSON Schema 校验；
- 高风险或低置信度告警应保留人工复核；
- LLM 更适合解释、复核和协作，而不是作为唯一检测机制。

---

## 4. 传统日志序列异常检测基础

### 4.1 DeepLog

**Du, M., Li, F., Zheng, G., & Srikumar, V. (2017). _DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning_. ACM CCS 2017.**

- 论文：[PDF](https://www2.cs.utah.edu/~lifeifei/papers/deeplog.pdf)
- DOI：[10.1145/3133956.3134015](https://doi.org/10.1145/3133956.3134015)

DeepLog 使用 LSTM 从正常日志中学习事件序列，通过预测下一事件发现异常，并支持一定的诊断分析。

对 SentinelFlow 的启示：

- 使用滑动窗口；
- 从正常调用流程学习顺序；
- 对会话建立独立上下文；
- 将“未出现于合理下一事件集合”作为序列异常候选；
- 适合建立无 LLM 的传统基线。

---

### 4.2 LogAnomaly

**Meng, W., Liu, Y., Zhu, Y., Zhang, S., Pei, D., Liu, Y., Chen, Y., Zhang, R., Tao, S., Sun, P., & Zhou, R. (2019). _LogAnomaly: Unsupervised Detection of Sequential and Quantitative Anomalies in Unstructured Logs_. IJCAI 2019.**

- 论文：[IJCAI PDF](https://www.ijcai.org/Proceedings/2019/0658.pdf)
- DOI：[10.24963/IJCAI.2019/658](https://doi.org/10.24963/IJCAI.2019/658)

LogAnomaly 明确区分：

- Sequential anomaly：事件顺序偏离正常执行流程；
- Quantitative anomaly：事件数量、出现次数或频率异常。

对 SentinelFlow 的映射：

| LogAnomaly | SentinelFlow |
|---|---|
| Sequential anomaly | 调用序列异常、重放 |
| Quantitative anomaly | 接口滥用、参数遍历 |
| Template semantics | API 路径和参数语义 |

这篇论文适合支撑 SentinelFlow 同时分析序列和数量特征的理论动机。

---

### 4.3 HitAnomaly

**Huang, S., Liu, Y., Fung, C., He, R., Zhao, Y., Yang, H., & Luan, Z. (2020). _HitAnomaly: Hierarchical Transformers for Anomaly Detection in System Log_. IEEE Transactions on Network and Service Management, 17(4), 2064–2076.**

- DOI：[10.1109/TNSM.2020.3034647](https://doi.org/10.1109/TNSM.2020.3034647)

HitAnomaly 使用层次化 Transformer，同时建模日志模板和参数值。

对 SentinelFlow 的启示：

- API Path 序列与 Body 参数需要分别建模；
- 参数不应被日志模板化过程完全删除；
- 参数值和调用顺序可以分别提取特征，再在候选层汇合；
- profile_id、sid、posid、count 等字段是重要安全证据。

---

### 4.4 LogBERT

**Guo, H., Yuan, S., & Wu, X. (2021). _LogBERT: Log Anomaly Detection via BERT_. IJCNN 2021.**

- 论文：[arXiv:2103.04475](https://arxiv.org/abs/2103.04475)
- DOI：[10.1109/IJCNN52387.2021.9534113](https://doi.org/10.1109/IJCNN52387.2021.9534113)

LogBERT 使用自监督任务学习正常日志序列，减少对异常标签的依赖。

对 SentinelFlow 的启示：

- 可以只使用可信正常数据建立行为基线；
- 适合构建 Transformer 异常检测基线；
- 自监督方法可作为未来扩展，但不是 MVP 必需项。

---

### 4.5 NeuralLog

**Le, V., & Zhang, H. (2021). _Log-based Anomaly Detection Without Log Parsing_. ASE 2021.**

- 论文：[arXiv:2108.01955](https://arxiv.org/abs/2108.01955)

NeuralLog 指出日志解析错误可能由未登录词和语义误解产生，进而导致异常检测丢失重要信息，因此直接从原始日志提取语义表示。

对 SentinelFlow 的启示：

- 不应过度压缩 API 请求体；
- 规范化必须保留安全相关参数；
- 可以移除随机 nonce 等无关字段，但必须通过明确配置；
- 原始事件应保留以支持证据追溯。

---

## 5. 评测设计和数据风险

### 5.1 LightAD：深度学习未必优于简单方法

**Yu, B., Yao, J., Fu, Q., Zhong, Z., Xie, H., Wu, Y., Ma, Y., & He, P. (2024). _Deep Learning or Classical Machine Learning? An Empirical Study on Log-Based Anomaly Detection_. ICSE 2024.**

- 论文：[PDF](https://boxiyu.github.io/assets/pdf/LightAD.pdf)
- DOI：[10.1145/3597503.3623308](https://doi.org/10.1145/3597503.3623308)
- 状态：ICSE 2024 正式论文。

#### 主要意义

该工作发现：

- 复杂日志预处理和深度模型不一定带来优势；
- 简单模型可以在常用数据集上获得很高结果；
- 多个常用日志数据集包含大量重复序列；
- 数据泄漏可能让非常简单的匹配方法取得异常高的 F1；
- 标签粒度和窗口聚合方式不匹配会破坏评测有效性。

#### 对 SentinelFlow 的要求

- 必须建立纯规则和简单统计基线；
- 不能只报告 LLM 或复杂模型结果；
- 数据集应按随机种子、时间或场景拆分；
- 必须检查训练集和测试集的重复模式；
- 请求级标签不能随意使用窗口级方法重新解释；
- 同一数据集不能既用于调 Prompt，又作为最终盲测成绩。

---

### 5.2 公共日志数据集的批判性评估

**Landauer, M., Skopik, F., & Wurzenberger, M. (2024). _A Critical Review of Common Log Data Sets Used for Evaluation of Sequence-Based Anomaly Detection Techniques_. Proceedings of the ACM on Software Engineering, 1(FSE), 1354–1375.**

- DOI：[10.1145/3660768](https://doi.org/10.1145/3660768)
- 状态：FSE 2024 正式论文。

该研究分析 HDFS、BGL、Thunderbird、OpenStack 和 Hadoop 等数据集，指出很多异常并不真正表现为序列异常，简单方法也可以取得很高的检测率。

对 SentinelFlow 的要求：

- 合成数据必须加入困难正常样本；
- 必须区分慢速遍历、合法分页和普通配置错误；
- 必须加入合法高峰、SDK 重试和共享 IP；
- 必须使用纯正常数据专门测 FPR；
- 需要报告每类异常，而不能只报告总体指标；
- 在真实数据上验证前，不应声称生产级泛化能力。

---

### 5.3 日志表示方式的经验研究

**Wu, X., Li, H., & Khomh, F. (2023). _On the Effectiveness of Log Representation for Log-based Anomaly Detection_. Empirical Software Engineering.**

- 论文：[arXiv:2308.08736](https://arxiv.org/abs/2308.08736)

该研究比较多种日志表示、机器学习模型和公开数据集，发现表示方式会显著影响下游结果；简单的 Message Count Vector 在许多实验组合中具有很强的竞争力。

对 SentinelFlow 的启示：

- 请求计数、路径计数和参数基数等简单特征不能省略；
- BERT 或 LLM Embedding 不应被默认视为最佳表示；
- 应进行以下消融：
  - 原始 API 事件；
  - 统计特征；
  - 文本/语义表示；
  - 统计特征 + LLM；
- 模型复杂度和性能提升必须分别报告。

---

### 5.4 自动化日志分析综述

**He, S., He, P., Chen, Z., Yang, T., Su, Y., & Lyu, M. R. (2021). _A Survey on Automated Log Analysis for Reliability Engineering_. ACM Computing Surveys, 54(6).**

- DOI：[10.1145/3460345](https://doi.org/10.1145/3460345)
- 公开版本：[arXiv:2009.07237](https://arxiv.org/abs/2009.07237)

该综述覆盖日志生成、压缩、解析、异常检测、故障预测和诊断，适合作为日志分析领域的整体背景来源。

---

## 6. LLM 在安全领域中的应用

### 6.1 LLM4Security 系统性文献综述

**Xu, H., Wang, S., Li, N., Wang, K., Zhao, Y., Chen, K., Yu, T., Liu, Y., & Wang, H. (2024). _Large Language Models for Cyber Security: A Systematic Literature Review_.**

- 论文：[arXiv:2405.04760](https://arxiv.org/abs/2405.04760)

该综述分析 LLM 在以下安全任务中的应用：

- 漏洞检测；
- 恶意软件分析；
- 网络入侵检测；
- 钓鱼检测；
- 主动防御和威胁狩猎。

综述指出的重要挑战包括：

- 数据集规模和多样性不足；
- 解释性不足；
- 数据隐私和安全风险；
- 缺少具有代表性的真实环境评测；
- 需要领域微调、迁移学习或安全专用预训练。

这篇论文适合作为 SentinelFlow 的安全领域背景综述来源。

---

### 6.2 ChatGPT 在漏洞管理中的能力评估

**Liu, P., Liu, J., Fu, L., Lu, K., Xia, Y., Zhang, X., Chen, W., Weng, H., Ji, S., & Wang, W. (2024). _Exploring ChatGPT's Capabilities on Vulnerability Management_. USENIX Security 2024.**

- 论文页：[USENIX Security 2024](https://www.usenix.org/conference/usenixsecurity24/presentation/liu-peiyu)
- 公开 PDF：[USENIX PDF](https://www.usenix.org/system/files/usenixsecurity24-liu-peiyu.pdf)

该工作在包含 70,346 个样本的数据集上评估 ChatGPT 完成六类漏洞管理任务的能力。

与 SentinelFlow 相关的观察：

- 随机选择 Few-shot 示例不能稳定提升性能；
- LLM 可能误解或错误使用 Prompt 中的信息；
- 自启发式地从示例中提取专业知识可能更有效；
- LLM 的不同安全任务能力存在明显差异。

对 Security Skill 的启示：

- 示例必须经过选择和版本化；
- Prompt 内容不是越多越好；
- 需要分别测试无 Skill、固定 Skill 和 Few-shot Skill；
- 每个 Skill 版本都要记录并重新评测。

---

### 6.3 PentestGPT：安全 Agent 架构参考

**Deng, G., et al. (2024). _PentestGPT: Evaluating and Harnessing Large Language Models for Automated Penetration Testing_. USENIX Security 2024.**

- 公开 PDF：[USENIX PDF](https://www.usenix.org/system/files/usenixsecurity24-deng.pdf)

PentestGPT 将复杂渗透测试任务拆为：

- Reasoning Module；
- Generation Module；
- Parsing Module；
- Pentesting Task Tree。

它与 SentinelFlow MVP 的异常检测任务不同，但可用于未来 Agent 化升级：

- 将输入解析、状态维护和安全推理分离；
- 使用结构化状态避免长上下文遗忘；
- 不让一个 Prompt 同时承担所有职责；
- 给调查过程建立显式任务树。

---

## 7. 文献对 SentinelFlow 架构的共同支持

综合以上研究，SentinelFlow 适合采用如下架构：

```text
API 请求日志
  |
  +-- 确定性数据处理
  |     +-- 时间和顺序
  |     +-- 访问频率
  |     +-- 参数基数与分布
  |     +-- 请求指纹
  |     +-- actor/session/resource 关系
  |
  +-- 候选异常检测
  |     +-- 越权冲突
  |     +-- 调用流程违反
  |     +-- 参数遍历
  |     +-- 高频接口滥用
  |     +-- 请求重放
  |     +-- 参数异常
  |
  +-- LLM + API Security Skill
        +-- 复核候选
        +-- 排除正常替代解释
        +-- 固定 taxonomy 分类
        +-- 组织可验证证据
        +-- 生成可解释告警
```

### 7.1 程序应承担的职责

根据 DeepLog、LogAnomaly、LightAD、MINES 等工作：

- 精确计算请求次数和时间间隔；
- 维护事件顺序；
- 关联会话和资源；
- 计算参数变化模式；
- 生成请求指纹；
- 运行候选规则和不变量；
- 校验告警输出；
- 计算 Precision、Recall、FPR 和 F1。

### 7.2 LLM 应承担的职责

根据 LogPrompt、LogGPT、MINES 和安全事件响应研究：

- 解释复杂业务语义；
- 综合不同证据；
- 复核候选是否合理；
- 区分异常类别；
- 分析正常替代解释；
- 生成面向安全分析师的告警说明；
- 在证据不足时降低置信度或拒绝判断。

### 7.3 LLM 不应承担的职责

- 从数千条日志中自行精确计算频率；
- 猜测未提供的资源归属；
- 自由创造异常类别；
- 在没有请求证据时生成告警；
- 访问 Ground Truth；
- 直接执行封禁、删除或其他高风险处置；
- 输出不可验证的隐藏推理作为唯一解释。

---

## 8. 对照实验设计

根据现有研究，建议至少设置三组：

### 8.1 纯规则

输入：

- 时间窗口；
- 参数统计；
- 请求指纹；
- 资源归属；
- 调用状态机。

输出：

- 固定规则告警。

目的：

- 建立低成本基线；
- 证明简单方法的能力；
- 防止把容易检测的合成模式错误归功于 LLM。

### 8.2 纯 LLM

输入：

- 连续日志窗口；
- 简单字段说明；
- 固定输出 Schema。

输出：

- LLM 直接分类和解释。

目的：

- 对照 LogGPT 和 LogPrompt；
- 测量 LLM 在无确定性候选辅助下的能力；
- 观察计算错误、遗漏和幻觉。

### 8.3 混合方法

输入：

- 确定性候选；
- 统计特征；
- 相关原始请求；
- 正常业务基线；
- Security Skill。

输出：

- LLM 复核后的结构化告警。

核心研究问题：

> 与纯规则和纯 LLM 相比，确定性候选检测与 API Security Skill 约束的 LLM 复核，是否能在越权、参数遍历和接口滥用检测中提高 Recall、降低 FPR，并改善告警解释质量？

---

## 9. 潜在研究空白

基于当前聚焦检索，可以暂时提出以下潜在空白：

1. 传统日志异常检测主要关注日志模板、事件序列和故障模式；
2. LLM 日志研究主要关注通用系统日志分类、解析和解释；
3. Web API 异常研究更多关注数据库一致性、Web 篡改和业务不变量；
4. 安全事件 LLM 研究更多关注告警总结、调查和漏洞管理；
5. 同时联合认证主体、资源归属、会话序列、参数分布和访问频率的研究相对有限；
6. 使用可版本化 Security Skill 约束 LLM 复核 API 行为并生成请求级证据告警的研究仍不充分；
7. 检出率、FPR、告警解释质量和 LLM 成本的联合评测仍值得研究。

建议在正式论文中谨慎表述为：

> 现有工作尚未充分研究一种面向 HTTP API 行为审计的混合框架：由确定性程序提取请求序列、参数分布、身份关系和访问模式特征，再由领域 Skill 约束的大语言模型进行候选复核、异常分类和证据化解释。

在完成更系统的检索之前，不应使用“首个”或“首次”等绝对创新性表述。

---

## 10. 推荐阅读顺序

### 第一组：直接理解 SentinelFlow 的研究定位

1. [MINES](https://arxiv.org/abs/2512.06906)
2. [WebNorm](https://doi.org/10.1145/3691620.3695024)
3. [LogAnomaly](https://www.ijcai.org/Proceedings/2019/0658.pdf)
4. [LogPrompt](https://arxiv.org/abs/2308.07610)

### 第二组：理解传统序列异常检测

5. [DeepLog](https://www2.cs.utah.edu/~lifeifei/papers/deeplog.pdf)
6. [HitAnomaly](https://doi.org/10.1109/TNSM.2020.3034647)
7. [LogBERT](https://arxiv.org/abs/2103.04475)
8. [NeuralLog](https://arxiv.org/abs/2108.01955)

### 第三组：理解 LLM 检测与解释

9. [LogGPT: Exploring ChatGPT](https://arxiv.org/abs/2309.01189)
10. [LogGPT: Log Anomaly Detection via GPT](https://arxiv.org/abs/2309.14482)
11. [LogLLM](https://arxiv.org/abs/2411.08561)
12. [Retrieval-Augmented LLMs for Security Incident Analysis](https://arxiv.org/abs/2603.18196)

### 第四组：理解评测风险

13. [LightAD](https://doi.org/10.1145/3597503.3623308)
14. [A Critical Review of Common Log Data Sets](https://doi.org/10.1145/3660768)
15. [On the Effectiveness of Log Representation](https://arxiv.org/abs/2308.08736)

### 第五组：理解 LLM 在安全领域中的作用与边界

16. [Large Language Models for Cyber Security: A Systematic Literature Review](https://arxiv.org/abs/2405.04760)
17. [Integrating LLMs into Security Incident Response](https://www.usenix.org/conference/soups2025/presentation/kramer)
18. [Exploring ChatGPT's Capabilities on Vulnerability Management](https://www.usenix.org/conference/usenixsecurity24/presentation/liu-peiyu)
19. [PentestGPT](https://www.usenix.org/system/files/usenixsecurity24-deng.pdf)

---

## 11. 后续文献调研任务

- [ ] 使用 ACM、IEEE、Scopus 或 Web of Science 执行正式数据库检索；
- [ ] 记录每个数据库的查询语句、时间和命中数量；
- [ ] 对题目和摘要进行两阶段筛选；
- [ ] 使用 DOI 和标题去重；
- [ ] 对 MINES、WebNorm、LogPrompt 进行前向和后向引文追踪；
- [ ] 单独检索 BOLA/IDOR、API enumeration、API abuse 和 business logic abuse；
- [ ] 检索身份行为分析与 UEBA 领域论文；
- [ ] 检索安全告警解释质量的人工评价方法；
- [ ] 建立论文方法、数据集、指标、开源代码和局限性矩阵；
- [ ] 区分系统日志、操作系统 API Call 和 HTTP API；
- [ ] 核验所有预印本是否已有正式发表版本；
- [ ] 在论文写作前执行一次引用完整性检查。

---

## 12. 文献矩阵

| 工作 | 对象 | 序列 | 数量/频率 | 参数语义 | LLM | 可解释 | 与本项目相关度 |
|---|---|---:|---:|---:|---:|---:|---:|
| DeepLog | 系统日志 | 是 | 弱 | 否 | 否 | 有限 | 中 |
| LogAnomaly | 系统日志 | 是 | 是 | 模板语义 | 否 | 有限 | 高 |
| HitAnomaly | 系统日志 | 是 | 部分 | 是 | Transformer | 有限 | 高 |
| LogBERT | 系统日志 | 是 | 部分 | 是 | 预训练 LM | 有限 | 中 |
| NeuralLog | 原始日志 | 是 | 部分 | 是 | 预训练语义模型 | 有限 | 中 |
| LogPrompt | 系统日志 | 是 | 部分 | 是 | 是 | 是 | 高 |
| LogGPT/ChatGPT | 系统日志 | 是 | 部分 | 是 | 是 | 是 | 高 |
| LogGPT/GPT+RL | 系统日志 | 是 | 是 | 有限 | 是 | 有限 | 中 |
| LogLLM | 系统日志 | 是 | 部分 | 是 | 是 | 有限 | 高 |
| WebNorm | Web 行为 | 是 | 部分 | 是 | 否 | 是 | 很高 |
| MINES | Web API/数据库 | 是 | 部分 | 是 | 是 | 是 | 很高 |
| RAG Incident Analysis | 多源安全日志 | 是 | 部分 | 是 | 是 | 是 | 很高 |
| SentinelFlow 计划 | HTTP API | 是 | 是 | 是 | 是 | 是 | — |

---

## 13. 引用注意事项

1. 两篇 LogGPT 标题接近但方法不同，引用时必须注明作者或方法；
2. arXiv 论文在正式写作前应再次检查是否已有会议或期刊版本；
3. 厂商对 API Abuse Detection 的说明可用作产业背景，但不能替代同行评审论文；
4. HDFS、BGL 等数据集的高 F1 不应直接解释为真实 API 安全效果；
5. 论文中的 API Call 可能指操作系统 API，需要阅读数据对象定义；
6. 不应从单篇论文的自报指标直接比较模型，必须确认数据拆分、标签粒度和评测单位；
7. SentinelFlow 的最终实验应公开随机种子、配置、Prompt/Skill 版本和数据 Manifest。
