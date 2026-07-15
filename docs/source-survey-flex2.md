# FLEX2 数据源实测记录

**日期**：2026-07-15
**平台侧**：`prometheus`，Ubuntu 24.04
**仪器**：Nova Biomedical BioProfile FLEX2，Analyzer ID `T281240040C`
**手册**：PN57960C（2017 版，**与实机固件有出入，以本文实测为准**）

> 本文记录的是**实测结论**，不是推测。每一条都是敲命令试出来的。
> 有推测成分的地方会明确标注。

---

## 1. 网络与共享

| 项 | 值 |
|---|---|
| Bridge PC IP | `10.0.13.66` |
| 机器名 | `FLEXIIINTERFACE`（局域网无 WINS/DNS，**名字解析不了，一律用 IP**） |
| 共享 | `\\FLEXIIINTERFACE\Export` |
| SMB 方言 | SMB1 ~ **3.1.1**（用 3.0 即可） |
| 网络路径 | `//10.0.13.66/Export` |

**⚠️ SMB1 仍启用**（`NT LM 0.12 (SMBv1) [dangerous, but default]`）。我方不使用，但属安全隐患，应报 IT 登记。

### 共享权限的实际状态

- **共享权限**：`Everyone` = Full Control / Change / Read **全部允许**
- **但** Windows「密码保护的共享」**开着** → 匿名访问被拒（`NT_STATUS_ACCESS_DENIED`）

即：**一道锁 + 锁后面完全敞开**。只要能认证上任意本地账号，`Everyone` 规则就会放行。

**🚫 不要动共享权限，不要关密码保护：**
- FLEX2 主机很可能**通过网络往 Bridge PC 这个共享写文件**。改 `Everyone` 可能让 Auto Export **当场瘫痪且不报错**
- 关掉密码保护 + `Everyone Full Control` = 整个局域网任何人都能删仪器数据
- **当前唯一的保护就是那道密码锁**

### 账户

| 账户 | 结论 |
|---|---|
| `novaservice` | ❌ Nova 服务工程师账户，**密码每天变**，不可用于自动化 |
| `nova_export_reader` | ✅ 我方新建，普通用户（`C$` 访问被拒 = 非管理员），只读用途 |

**只读如何保证**：共享权限动不得（`Everyone` 会给任何账号 Full Control），
所以**从 Linux 侧锁死** —— 挂载加 `ro`，内核层面不发写请求。脚本启动时再自验一次。

**⚠️ 待办**：Bridge PC 上给 `nova_export_reader` 勾**「密码永不过期」**，
去掉「用户下次登录时须更改密码」。否则 42 天后定时任务静默全挂。

### 验证过的命令

```bash
nc -zv 10.0.13.66 445                                    # succeeded
nmap -p445 --script smb-protocols 10.0.13.66             # 列出 dialects 到 3.1.1
smbclient -L //10.0.13.66 -N                             # ACCESS_DENIED（匿名列清单被禁，正常）
smbclient -L //10.0.13.66 -U nova_export_reader          # ✅ 列出 Export
smbclient //10.0.13.66/C\$ -U nova_export_reader         # ACCESS_DENIED ✅（证明非管理员）
smbclient //10.0.13.66/Export -U nova_export_reader -m SMB3   # ✅
```

---

## 2. 共享目录结构（与手册不符）

手册说 Export 下是 `Logs` + `Results`。**实际是：**

```
Export/
├── Results/          ← 结果 CSV
├── Database/         ← 手册未提。每晚 23:30 数据库备份
└── Report/           ← 手册未提。人工导出的 PDF
```
（`Logs/` 不存在）

C:\ 根目录另有 `OPC_` 目录 → **FLEX2 可能有 OPC 接口**，值得问 Nova（实时取数通道，比抓 CSV 高级）。
另有 `生化分析仪数据备份 - Shortcut`（2025-08-18）→ **可能已有人做过备份配置，须查清，别撞车**。

磁盘：128 GB，剩余约 106 GB。**未发现自动清理**（2024 年文件仍在）。

---

## 3. Results/ 里的两套文件

### 关键发现：两种导出的格式**不一样**

| | 逐次导出 | 月度累积 |
|---|---|---|
| 文件名 | `SampleResultsT281240040C2026-07-15_152602.csv` | `SampleResultsT281240040C2026-July.csv` |
| 列数 | **34** | **40** |
| 数据行引号 | **不加** | **全加** |
| 独有列 | — | `Comment`、`Pre-Dilution Multiplier`、`RSM`、**4 个试剂批号列** |
| 是否变化 | 写完不变（immutable） | **整月持续追加** |

### 🔴 列顺序被打乱了

```
逐次： ... pH @ Temp, PCO2 @ Temp, PO2 @ Temp ...
月度： ... pH @ Temp, PO2 @ Temp, PCO2 @ Temp ...      ← 互换

逐次： ... Chemistry Flow Time, pH / Gas Flow Time ...
月度： ... pH / Gas Flow Time, Chemistry Flow Time ...  ← 互换
```

**按列位置解析 = PO2/PCO2 静默调包。** 不报错、数值合理、发现不了。
→ **铁律：按列名映射。**

### 月度独有的试剂批号（GMP 价值所在）

```
"Chemistry Cartridge Lot Number"  26071060
"Chemistry Card Lot Number"       26057032
"Gas Cartridge Lot Number"        26124043
"Gas Card Lot Number"             25339017
```
**逐次文件完全没有这四列。** 试剂批号 → 检测结果的可追溯链，只有月度文件有。
这是"月度 = 主数据源"的决定性理由。

### 逐次文件的来源（已查明）

同事不知道 Auto Export 有效，**每天手动点导出**。已确认 Auto Export 现在是勾着的，
将告知同事停止手动导出。→ **今后只有月度文件。**

逐次文件里重复很多（双击导出）：
```
2026-01-04_150005.csv  129837
2026-01-04_150018.csv  129837   ← 13 秒后，一模一样
```
另有一个残留的 `SampleResultsT281240040C2025-11-25_103557.csv - Shortcut.lnk`（人手工留下的）。
→ 文件名正则须严格锚定 Analyzer ID，避开这类杂物。

### ⚠️ "月度是逐次的严格超集" —— 验证强度不足

对比过**一条**记录（`FBC_SN_D2` / `7/15/2026 8:41:15`），两边**字段完全一致**，
且月度里 `Vessel ID` / `Batch ID` / `Cell Type` 分得清清楚楚（`A6_A6` / `R2601` / `0092`）。

**但样本量是 1，不是 280 个文件、14 个月的证明。**
→ 待办：`--verify-coverage` 做一次性全量核对，通过后才正式弃用逐次文件。

> 补充：7/1 的月度记录里出现过 `Batch ID = "015_R2602_B3_B3"`（三个字段被拼成一串），
> 一度以为是格式问题。对比后确认是**操作员录入习惯**，不是导出行为。属 SOP 问题。

---

## 4. CSV 格式细节（全部实测）

| 项 | 值 |
|---|---|
| 编码 | **UTF-8，无 BOM**（`head -c 3` = `"Da`） |
| 时间制 | **24 小时制**（`6/15/2026  18:26:07` 验证于 20:01 导出的文件），**无 AM/PM 歧义** |
| 日期格式 | `M/D/YYYY`，日期与时间之间**两个空格** |
| 行尾 | **每行末尾多一个逗号** → 产生一个空列，属正常 |
| 表头 | 非 ASCII（`Vessel Temperature (°C)`） |
| 空值 | 未测的参数留空 |
| 重复行 | **0**（月度文件内部无重复；2026-July 共 203 行） |
| 数据密度 | 约 13–14 样/天；全年约 5000 条 —— **对数据库是毛毛雨** |

### 月度文件 40 列（顺序即实际顺序）

```
Date & Time, Comment, Sample ID, Sample Type, pH, PO2, PCO2, Gln, Glu, Gluc, Lac,
NH4+, Na+, K+, Ca++, Pre-Dilution Multiplier, Vessel ID, Batch ID, Cell Type,
Vessel Temperature (°C), Vessel Pressure (psi), Sparging O2%, pH @ Temp, PO2 @ Temp,
PCO2 @ Temp, O2 Saturation, CO2 Saturation, HCO3, pH / Gas Flow Time, Chemistry Flow Time,
Chemistry Dilution Ratio, RSM, Tray Location, Chemistry Cartridge Lot Number,
Chemistry Card Lot Number, Gas Cartridge Lot Number, Gas Card Lot Number,
Time In Tray, Sample Time, Operator,
```
（末尾逗号 → 第 41 个空列）

**列映射已交叉验证**：用 Henderson-Hasselbalch 反算 HCO3 对上了
（pH 7.171 / PCO2 119.8 → 0.03×119.8×10^1.071 = 42.3，文件里 42.5 ✓）

---

## 5. 数据覆盖范围

| 文件 | 最早 |
|---|---|
| `QcResults` 月度 | **2024-01** |
| `SampleResults` 月度 | **2025-05** |
| 逐次文件 | 2025-08-16 |

**推测**（未证实）：2024 装机验收跑 QC，2025-05 才进入常规样品使用。
或 Auto Export 那时才打开。
→ **待确认**：2025-05 之前是否做过样品？若做过，那些数据只在仪器加密数据库里，共享盘一份都没有。

### 停机是常态 —— 直接影响告警设计

```
2025-08 ~ 2026-01   几乎每天有，周末也不停
2026-01-23 → 02-05  空 13 天
2026-02-10 → 03-03  空 21 天
```
**"样品数据多久没更新"这个告警在这台仪器上是废的**，只会天天误报。
→ 健康信号改用 **Database 备份新鲜度**（每晚固定跑，与做不做样品无关）。

---

## 6. Database/ 备份

```
Database/
└── Backup_2026-07-14_233019/     ← 只有一个 = 每晚覆盖，retention 1
      ├── DatabaseBackup.dbb   14,635,660 B (~14 MB)
      └── Persist.dbb              21,947 B
```

### `.dbb` = 7z 容器 + **AES 加密**

```
377a bcaf 271c    ← 7z 签名
Method = LZMA2:384k 7zAES    ← 内容 AES 加密
```
文件头未加密（`7z l` 可列清单），**内容加密**（解压需 Nova 持有的密码）。
→ **已停手，未尝试破解。**

### `Persist.dbb` 内含（60 个文件，从文件名可见）

**是配置与状态，不是结果数据**：
- `Sequencing/SequenceManager_DP_ChemCal.xml` —— 化学校准数据（7/14 22:31 更新）
- `Sequencing/SequenceManager_DP_GasCal.xml` —— 气体校准数据
- `Operations/{QC,Calibration,Maintenance,Warranty}.PersistentTasks.xml` —— 计划状态
- `DataStore/AutoComplete.xml` —— 样品 ID 自动补全列表（手册 3.4.5）
- `DataStore/UserData.xml` —— 用户账户
- `Sequencing/SequenceManager_DP_ProbeGeometry.xml` —— 探针几何
- `Digest.txt` —— 完整性摘要

**推测**：`DatabaseBackup.dbb`（14 MB）才是结果数据库本体。

> 大量成员日期为 `2019-04-11` = 出厂镜像默认值。
> 与 `install.log`(2018-06)、`Windows\`(2019-02) 一致 —— **设备 2024 年购入，跑的是 2019 年的系统镜像**。
> 也解释了 SMB1 为何还开着。

### 定位

- ❌ 不做数据源：私有格式 + 加密 + 无文档 + 无厂商承诺 + 固件升级可能变 → GMP 环境无法验证
- ✅ **每日归档做灾备**：14 MB/天 ≈ 5.4 GB/年，白菜价。**里面有校准数据和 QC 状态，是 GxP 相关的**，
  而 Nova 自己只留一份，不抓就没了

**⚠️ 但必须问 Nova**：一份自己打不开、只能求厂商的备份，
**恢复时由谁、用什么工具解密？密钥丢失时会不会变成死数据？**
这个不问清楚，等于买了份不知道能不能理赔的保险。

---

## 7. 手册（PN57960C）中已证伪/已过时的部分

| 手册说 | 实际 |
|---|---|
| Export 下有 `Logs` + `Results` | 是 `Results` + `Database` + `Report`，无 `Logs` |
| 访问共享无需账号（步骤里只说"点进去"） | 密码保护开着，必须认证 |
| 无 `Database` / `Report` 目录的任何描述 | 都存在，且 `Database` 是关键灾备资产 |
| 3.4.1 设置项里无网络配置 | 一致（确实没有） |

**手册中仍成立的**：
- 无 sample list / worklist 导入功能（不能从 Excel 预填样品名；只有条码或手输）
- 无 LIMS/host 双向接口、无 ASTM/HL7
- 导出格式为 `.csv`；单条结果可导 PDF
- 「Enable Sample Results Auto Export」在 `Settings → General`
- Analyzer ID 在 `Settings → General`（≥ Intermediate 权限）
- 3.4.1.11 有 Use Network Time —— **建议启用**，保证时间戳可比对
