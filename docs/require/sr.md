# Barra CNE5 LEAN集成实现需求文档

## 一、项目概述

### 1.1 项目目标
在LEAN量化交易框架内紧密耦合实现Barra CNE5多因子模型，支持回测和live-paper交易，并为后续Barra CNE6及其他量化策略扩展奠定架构基础。

### 1.2 核心原则
1. **紧密耦合原则**：深度集成LEAN框架，避免构建独立系统
2. **效率优先原则**：C#/Python选择以性能和LEAN架构耦合度为准
3. **Token节约原则**：大计算量工作离线预计算，程序仅处理轻量级任务
4. **可扩展原则**：架构设计支持未来新因子模型和策略的快速接入

### 1.3 约束条件
- **禁止**直接读取 `/home/project/ccleana/data/tushare_data` 原始数据
- **最小化**读取LEAN框架源码（仅在必要时参考）
- 复用已有数据映射关系（`Barra-CNE5-Data-Mapping.md`）

---

## 二、需求分析

### 2.1 前期设计回顾要求

请Sonnet完成以下分析任务：

1. **对比前三版设计文档**：
   - `docs/design/Barra-CNE5-System-Design.md`（v1）
   - `docs/design/Barra-CNE5-System-Design-v2.md`（v2）
   - `docs/design/Barra-CNE5-System-Design-v3.md`（v3）
   
   **分析重点**：
   - 各版本与LEAN框架的耦合程度演化
   - 数据流设计的优化路径
   - 计算任务分离方案的成熟度

2. **对比前三版工作分解**：
   - `docs/design/Barra-CNE5-Work-Breakdown.md`（v1）
   - `docs/design/Barra-CNE5-Work-Breakdown-v2.md`（v2）
   - `docs/design/Barra-CNE5-Work-Breakdown-v3.md`（v3）
   
   **分析重点**：
   - 人工计算与程序计算的边界划分合理性
   - 任务依赖关系的清晰度
   - 工作量估算的准确性

### 2.2 现有资源评估

#### 2.2.1 数据资源
- **原始数据位置**：`/home/project/ccleana/data/tushare_data/`
- **数据字典**：
  - `misc/tushare-dir.json`（表头信息）
  - `misc/tushare-net.json`（字段说明）
  - `docs/design/Barra-CNE5-Data-Mapping.md`（因子-数据映射）

#### 2.2.2 计算脚本
**位置**：`/home/project/ccleana/Leana/scripts/barra/`

**需要验证的问题**：
1. 现有Python脚本是否覆盖所有必要的因子计算？
2. 是否存在冗余或遗漏的计算任务？
3. 脚本输出与LEAN数据格式的对接是否完善？

#### 2.2.3 计算结果
**位置**：`/home/project/ccleana/data/barra_reports/`
- `validation_report.html`（总结报告）
- 其他因子计算过程文件

**验证任务**：
- 确认已完成的因子计算范围
- 识别未完成或需要补充的计算

#### 2.2.4 计划文档
**文件**：`.sisyphus/plans/barra-cne5-implementation.md`

**审查要点**：
- 人工启动的大数据量计算任务定义是否合理
- 计算触发时机设计（定时/事件驱动）
- 结果存储与程序调用接口规范

---

## 三、技术要求

### 3.1 LEAN框架集成

#### 3.1.1 必须学习的LEAN核心文档
- `docs/lean-core-principles/00-LEAN-Arch.md`

**关键理解点**：
1. LEAN的数据订阅机制（Universe Selection）
2. Alpha模型架构（Alpha Model）
3. 风险管理模块（Risk Management）
4. 执行模型（Execution Model）
5. 自定义数据源集成方式

#### 3.1.2 集成策略
```
优先级排序：
1. 使用LEAN原生组件（QCAlgorithm, Alpha Model等）
2. 扩展LEAN基类（继承BaseData, AlphaModel等）
3. 仅在不可避免时创建独立模块（需详细说明理由）
```

### 3.2 语言选择原则

| 模块类型 | 推荐语言 | 理由 |
|---------|---------|------|
| LEAN策略主体 | C# | LEAN核心是C#，紧密耦合需C# |
| 因子计算引擎 | Python | 利用NumPy/Pandas计算效率 |
| 数据预处理 | Python | 已有Tushare数据处理生态 |
| 回测逻辑 | C# | 复用LEAN回测引擎 |
| 定时任务调度 | Python | 配合现有scripts体系 |

### 3.3 性能要求
- 回测模式：支持日频/分钟频数据
- 实时模式：因子更新延迟 < 10秒（基于预计算数据）
- 内存占用：单策略实例 < 2GB

---

## 四、架构设计要求

### 4.1 第四版设计文档需包含

#### 4.1.1 系统分层架构
```
Layer 1: LEAN框架层（不修改）
Layer 2: Barra CNE5 适配层（紧密耦合）
   ├─ 数据适配器（将预计算结果转为LEAN格式）
   ├─ Alpha模型实现（继承AlphaModel）
   └─ 风险管理扩展（集成协方差矩阵）
Layer 3: 离线计算层（独立运行）
   ├─ 因子计算脚本（Python）
   ├─ 协方差矩阵估计
   └─ 特定风险计算
Layer 4: 数据存储层
   ├─ 预计算结果库（Parquet/HDF5）
   └─ 元数据管理（SQLite/JSON）
```

#### 4.1.2 数据流设计
```mermaid
graph LR
A[Tushare原始数据] -->|定时脚本| B[因子计算Python]
B -->|存储| C[预计算结果库]
C -->|LEAN数据适配器| D[LEAN Universe]
D -->|Alpha模型| E[投资组合构建]
E -->|回测引擎| F[绩效报告]
```

**关键节点说明**：
1. **定时脚本触发机制**（需详细设计）
2. **预计算结果库Schema**（需定义）
3. **LEAN数据适配器实现**（需指定基类）

#### 4.1.3 因子体系映射
基于 `Barra-CNE5-Data-Mapping.md`，需明确：

| Barra CNE5因子组 | 需要的Tushare数据表 | 计算脚本 | 更新频率 |
|-----------------|-------------------|---------|---------|
| Size（规模） | daily_basic, fina_indicator | ? | 日度 |
| Beta（贝塔） | daily, index_daily | ? | 日度 |
| Momentum（动量） | daily | ? | 日度 |
| ... | ... | ... | ... |

**待确认**：现有 `scripts/barra/*.py` 是否完整覆盖？

### 4.2 离线计算与在线程序对接设计

#### 4.2.1 计算任务审查
**审查对象**：`.sisyphus/plans/barra-cne5-implementation.md`

**验证问题**：
1. 定义的"大数据量计算"边界是否合理？（如何量化"大"）
2. 人工触发 vs 自动定时的判断标准是什么？
3. 计算失败的容错机制？

#### 4.2.2 现有脚本评估
**评估 `/home/project/ccleana/Leana/scripts/barra/*.py`**：

需要生成评估表：
```
脚本名称 | 计算的因子 | 是否必须 | 是否遗漏 | 输出格式 | 更新频率
--------|----------|---------|---------|---------|----------
xxx.py  | Size/Beta| 是      | -       | Parquet | 每日
...     | ...      | ?       | ?       | ?       | ?
```

#### 4.2.3 定时任务设计
**要求设计**：
- 使用何种调度器（cron/Airflow/APScheduler）？
- 任务依赖关系如何管理？
- 计算结果如何通知LEAN程序？
- 示例Cron表达式

---

## 五、工作分解要求

### 5.1 第四版工作分解结构

#### Phase 1: 架构验证与设计（1周）
- [ ] 深度学习LEAN架构文档
- [ ] 对比v1-v3设计，提炼最佳实践
- [ ] 评估现有计算脚本完整性
- [ ] 确认离线-在线对接方案
- [ ] 编写v4设计文档

#### Phase 2: 离线计算完善（2周）
- [ ] 补充遗漏的因子计算脚本
- [ ] 统一输出格式为LEAN可读格式
- [ ] 设计预计算结果存储Schema
- [ ] 实现定时任务调度系统
- [ ] 编写计算监控与告警

#### Phase 3: LEAN集成开发（3周）
**C# 部分**：
- [ ] 实现自定义UniverseSelectionModel
- [ ] 实现BarraCNE5AlphaModel（继承AlphaModel）
- [ ] 实现协方差矩阵风险管理器
- [ ] 集成Portfolio Construction Model

**Python 部分**：
- [ ] 编写LEAN数据适配器（读取预计算结果）
- [ ] 实现Python-C#数据桥接（若需要）

#### Phase 4: 回测与验证（2周）
- [ ] 构建历史数据回测场景
- [ ] 对比Barra官方因子表现
- [ ] 调优参数与风险控制
- [ ] 编写回测报告模板

#### Phase 5: Live-Paper部署（1周）
- [ ] 配置实时数据源
- [ ] 实现增量因子更新
- [ ] 监控系统部署
- [ ] Paper Trading验证

### 5.2 人工计算任务清单

**需明确**：
1. 哪些计算任务需要人工手动执行？
2. 执行频率（每日/每周/每月）？
3. 执行结果如何验证？
4. 如何与自动化流程对接？

**示例格式**：
```yaml
- 任务名: 协方差矩阵全量计算
  脚本: scripts/barra/covariance_matrix.py
  触发方式: 每周日23:00自动执行
  依赖: 所有因子数据已更新
  输出: data/barra_cache/cov_matrix_{date}.h5
  验证: 检查矩阵条件数 < 1000
  失败处理: 邮件告警 + 使用上周缓存
```

---

## 六、交付要求

### 6.1 文档交付物
1. **Barra-CNE5-System-Design-v4.md**
   - 完整架构图（Mermaid格式）
   - 每个模块的LEAN集成方式说明
   - C#/Python代码比例分配
   - 数据流转详细设计

2. **Barra-CNE5-Work-Breakdown-v4.md**
   - 详细任务清单（可直接分配给开发者）
   - 每个任务的技术要点
   - 依赖关系与时间估算
   - 人工计算任务调度表

3. **Barra-Scripts-Assessment.md**（新增）
   - 现有脚本完整性评估
   - 遗漏计算的补充方案
   - 脚本优化建议

4. **Offline-Online-Integration-Guide.md**（新增）
   - 定时任务配置手册
   - 数据格式规范
   - 故障排查流程

### 6.2 代码交付物（框架级）
- LEAN扩展基类定义（C#接口）
- 数据适配器示例代码
- 定时任务配置模板

---

## 七、验证标准

### 7.1 架构合理性
- [ ] 无独立系统，所有组件均在LEAN框架内或作为数据源
- [ ] C#代码占比 > 60%（策略核心逻辑）
- [ ] 离线计算结果可无缝加载到LEAN

### 7.2 可扩展性
- [ ] 新增因子仅需添加计算脚本 + 映射配置
- [ ] 支持切换到Barra CNE6仅需替换因子库
- [ ] 其他多因子模型可复用架构

### 7.3 性能达标
- [ ] 历史回测10年数据 < 30分钟
- [ ] Live-paper模式因子延迟 < 300秒

---

## 八、风险与假设

### 8.1 技术风险
1. **LEAN原生功能限制**：可能需要修改LEAN源码
   - 缓解：优先使用扩展机制，最小化侵入
   
2. **Python-C#互操作性能**：数据传输开销
   - 缓解：使用共享内存或预序列化格式

3. **大规模矩阵计算**：协方差矩阵估计可能OOM
   - 缓解：分块计算 + 稀疏矩阵优化

### 8.2 执行条件
1. Tushare数据质量稳定，无需额外清洗
2. LEAN框架版本为最新稳定版
3. 服务器资源充足（24GB RAM, 4 cores）

---

## 九、实施指导

### 给Sonnet的具体要求

1. **首先完成**：
   - 阅读 `docs/lean-core-principles/00-LEAN-Arch.md`
   - 对比 v1-v3 设计文档，总结演化脉络
   - 评估 `scripts/barra/*.py` 与因子映射表的一致性

2. **输出优先级**：
   - 先生成 **Barra-Scripts-Assessment.md**（验证基础）
   - 再生成 **System-Design-v4.md**（架构设计）
   - 最后生成 **Work-Breakdown-v4.md**（执行计划）

3. **设计原则**：
   - 每个设计决策需说明"为什么这样更贴合LEAN"
   - 明确标注C#/Python边界
   - 所有数据接口需定义Schema

4. **避免陷阱**：
   - ❌ 不要设计脱离LEAN的独立因子计算引擎
   - ❌ 不要直接读取 `tushare_data` 原始文件
   - ✅ 专注于"如何让预计算结果成为LEAN的数据源"

---

## 十、参考资料索引

| 文档类别 | 文件路径 | 用途 |
|---------|---------|------|
| LEAN架构 | `docs/lean-core-principles/00-LEAN-Arch.md` | 理解框架核心 |
| 数据映射 | `docs/design/Barra-CNE5-Data-Mapping.md` | 因子-数据对应 |
| 历史设计 | `docs/design/Barra-CNE5-System-Design[-v2/-v3].md` | 设计演化 |
| 历史分解 | `docs/design/Barra-CNE5-Work-Breakdown[-v2/-v3].md` | 任务演化 |
| 实施计划 | `.sisyphus/plans/barra-cne5-implementation.md` | 当前计划 |
| 数据字典 | `misc/tushare-dir.json` + `misc/tushare-net.json` | 数据理解 |
| 计算脚本 | `/home/project/ccleana/Leana/scripts/barra/*.py` | 现有实现 |
| 验证报告 | `/home/project/ccleana/data/barra_reports/validation_report.html` | 完成度 |

---

## 附录：特别说明

### A. Token节约策略
- 因子计算代码无需Sonnet生成（已有Python脚本）
- 大型配置文件采用"模板+说明"模式
- 重复性代码仅给出第一个示例

### B. 可扩展性验证案例
设计完成后，需要能回答：
> "如果要接入 Fama-French 五因子模型，需要改动哪些文件？新增哪些脚本？"

预期答案应明确且改动点 < 5个文件。

---

