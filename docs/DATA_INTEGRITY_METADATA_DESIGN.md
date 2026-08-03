# 原始文件 Metadata 采集设计说明

| | |
|---|---|
| 文档版本 | v1.0（2026-08-03） |
| 对应整改项 | `AUDIT-2026-08-03-data-integrity.md` **MD-001** |
| 适用范围 | Stage 1 采集程序（当前落地于 Vi-CELL；FLEX2 后续同步） |
| 本阶段**不**解决 | MD-002（元数据库）、MD-003（恢复验证）、备份看板 —— 均属后续阶段 |

---

## 1. 为什么需要 metadata 采集

### 1.1 问题陈述

审计（MD-001）发现：**Windows NTFS 的原始文件创建时间（CreationTime）从未被采集。**

这一点**不是文件复制失败**，也不是数据损坏。文件字节内容完整、SHA-256 双向校验全部通过。
问题是：**源端可以提供的元数据，原方案没有去取。**

### 1.2 为什么这在 GxP 语境下重要

FDA 检查中的典型追问是"你如何证明这份归档副本对应的原始文件，就是仪器当时产生的那一份、
且此后未被替换过"。回答这个问题需要多个独立佐证互相印证：

| 佐证 | 原方案 | 说明 |
|---|---|---|
| 内容一致 | ✅ SHA-256 双向校验 | 已有，且是最强的一环 |
| 业务时间 | ✅ 文件内部 `LogDate`/`RunDate`/`FileDate` | 已有（仅文本类数据文件有；图片没有） |
| 文件写入时间 | ✅ modified time | 已有 |
| **文件创建时间** | ❌ | **缺口** |

对**图片类资产**（Vi-CELL 的 TIF，约 13 万个）缺口尤其明显——图片内部不含业务时间戳，
一旦文件系统时间也丢失，就只剩"目录名等于样品名"这一条弱关联。

### 1.3 一个真实且有说服力的例子

本项目 2026-07 发生过一次人工搬移文件夹。实测同一个图片文件在两个位置的元数据：

```
D:\Vi-Cell 计数图像\0005m10\0005m10_10.tif      （软件当年真正写入的原始位置）
    creation_time : 2026-06-23 15:38:03    ← 原始创建时间完好
    modified_time : 2026-06-23 15:38:03

E:\Vi-Cell\Images\0005m10\0005m10_10.tif        （2026-07 人工拷贝的副本）
    creation_time : 2026-07-07 19:23:40    ← 被重置为拷贝当天
    modified_time : 2026-06-23 15:38:03    ← 修改时间仍是原始值
```

**创建时间恰恰是唯一能区分"原件"与"副本"的字段**，而它正是原方案丢掉的那个。
这也是本项目决定首次回补从 D 盘原始位置取数的直接依据。

### 1.4 时效性

原始位置（D 盘）一旦被清理，其创建时间将**永久不可恢复**。采集越早越好。

---

## 2. 采集哪些 metadata、用什么方法

### 2.1 方案选择：CIFS 扩展属性（已实测确认）

Linux 挂载 CIFS 后，`os.stat()` **拿不到**创建时间——`statx` 的 `st_birthtime` 返回 `None`，
`stat` 命令显示的 `Birth:` 是内核用 mtime 填充的假值（实测 `Birth == Modify` 逐秒相同）。

但 CIFS 客户端把创建时间**通过扩展属性暴露出来了**：

```python
raw = os.getxattr(path, "user.cifs.creationtime")   # 8 字节，Windows FILETIME 小端
# FILETIME = 自 1601-01-01 UTC 起的 100 纳秒数
epoch = struct.unpack("<Q", raw)[0] / 10_000_000 - 11644473600
```

**正确性验证**：解码结果与 `smbclient allinfo`（走 SMB 协议原生查询）**逐秒吻合**，
三个不同来源的文件全部一致（见 §6 测试报告 Test 1）。

**性能实测（冷读，未命中客户端缓存）**：**2.6 ms/文件** → 13 万文件约 6 分钟。
嵌入现有复制循环后，每个样品目录（50 个文件）仅增加约 0.13 秒，
相对当前 8 秒/目录的复制耗时可以忽略。

### 2.2 为什么不用 `smbclient allinfo` 作为默认方案

`smbclient allinfo` 同样能取到（且能多取 NTFS 属性），但作为**日常备份流程**不合适：

| 维度 | `os.getxattr` | `smbclient allinfo` |
|---|---|---|
| 性能 | **2.6 ms/文件** | 0.072 ms→ 实测边际 **72 ms/文件**（批量调用下） |
| 13 万文件耗时 | **约 6 分钟** | 约 2.6 小时 |
| 依赖 | **Python 标准库** | 外部命令 `smbclient`（samba-client 包） |
| 与项目约定 | 符合"Stage 1 只用标准库" | 需破例引入外部依赖 |
| 会话开销 | 复用已有挂载 | 每批新建 SMB 会话与认证 |

**结论：`os.getxattr` 为默认且唯一的采集方式。**
`smbclient allinfo` 仅保留为**交叉验证工具**（用于定期确认 xattr 解码正确性），不进入日常流程。

### 2.3 采集字段清单

| 字段 | 来源 | 成本 | 是否采集 |
|---|---|---|---|
| `file_size` | `os.stat().st_size` | 免费 | ✅ |
| `modified_time_original` | `os.stat().st_mtime` | 免费 | ✅ |
| `access_time_original` | `os.stat().st_atime` | 免费 | ✅（实测与 `allinfo` 的 access_time 一致） |
| `change_time_original` | `os.stat().st_ctime` | 免费 | ✅ 采集，但**标注可靠性**，见下 |
| `creation_time_original` | `getxattr user.cifs.creationtime` | 2.6 ms | ✅ |
| NTFS 属性（`A`/`H`/`R`） | 仅 `allinfo` | 72 ms | ❌ 本阶段不采集 |
| 属主 / ACL | `getxattr system.cifs_ntsd` | **201 ms** | ❌ 本阶段不采集 |

**关于 `change_time_original` 的可靠性说明**：Linux 的 `st_ctime` 语义是"inode 变更时间"，
CIFS 客户端将其映射自 SMB 的 `ChangeTime`。本设计**照实采集并记录**，但在文档与字段
`metadata_source` 中标注其来源为 `stat`，**不主张其与 Windows `ChangeTime` 在所有场景下严格等价**。
需要严格取值时以 `smbclient allinfo` 交叉核对为准。

**关于属主/ACL 不采集的说明**：实测 `system.cifs_ntsd` 可取到完整 NT 安全描述符，
但单文件耗时 **201 ms**（是创建时间的 77 倍），13 万文件需 7 小时以上。
且审计结论指出"ACL 是否需要保留取决于 QA 对本系统定位的认定，**尚未确定**"。
故本阶段不采集；若 QA 判定必需，再按共享级或抽样级单独设计。

---

## 3. 哪些 metadata 无法恢复（技术限制说明）

> **本节是 FDA 检查时的正式说明口径，请勿在代码或文档其它处暗示相反的意思。**

### 3.1 系统保存的是 Original Source Creation Time，不是 Backup File Creation Time

采集到的 `creation_time_original` 描述的是**源端文件在仪器工作站上的创建时间**。
它作为**独立证据记录**保存在 `Metadata/` 下的 CSV 中。

**NAS 归档副本自身的文件系统创建时间，必然是"归档发生的时刻"**，与源端无关。

### 3.2 为什么不尝试修改 NAS 副本的 CreationTime

**因为在 Linux 上做不到。** 这是操作系统层面的限制，不是实现选择：

- Linux **没有任何系统调用**可以设置文件的创建时间（birth time）。
  `utimes`/`futimens` 只能设置 atime 与 mtime。
- 换 Python 复制方法无效：`shutil.copy2` 也只复制 mtime/atime/mode，从不处理创建时间。
- 换数据源无效：无论从 D 盘还是 E 盘读取，写入端的限制不变。
- 唯一能保留该字段的路径是**在 Windows 侧用 robocopy 之类的工具复制**，
  这将推翻当前"仪器侧零安装、只读拉取"的架构，显著提高验证负担，**不予采用**。

**因此：本系统明确不尝试修改 NAS 文件的 CreationTime。**
正确做法是把原始 metadata 作为独立证据保存下来。

### 3.3 检查时的解释口径

> **Inspector**: *"Your backup copy shows a creation date of 2026-08-03, but the sample was run in June. Explain."*
>
> **回答**：归档副本的文件系统创建时间反映的是归档动作发生的时刻，这是文件复制的固有属性，
> 任何复制到新介质的副本都是如此。原始文件在仪器工作站上的创建时间，
> 我们作为独立元数据完整采集并保存，可以出示：`Metadata/<机器名>/<时间戳>_SMB_Metadata.csv`
> 中该文件的 `creation_time_original` 字段。该值来自 SMB 协议层，
> 并已与 `smbclient allinfo` 的原生查询交叉验证一致。
>
> 同时，同一份文件的字节内容一致性由 `Checksums/` 下的 SHA-256 双向校验记录证明；
> 两份记录可通过 `relative_path` + `source_path` + `file_size` 关联，
> 因此"创建时间"与"被校验过的那份字节"是绑定的，不是两条互不相关的记录。
>
> 我们**没有**、也**无法**修改归档副本的创建时间——Linux 文件系统不提供该接口。
> 这一限制在设计文档中有明确记载。

---

## 4. 输出方式

### 4.1 不修改现有产出物

`Checksums/` 下的 SHA-256 比对文件**格式与结构完全不变**。

原因不仅是向后兼容：该 9 列表头
`Relative_Path,Local_Path,NAS_Path,Change_Type,Local_Size,Local_MTime,Local_SHA256,NAS_SHA256,match_status`
是**跨仪器共用的既有约定**——实测 Biacore 的历史备份脚本使用完全相同的表头。
往里加列会破坏机群一致性，并可能打断下游解析。

### 4.2 新增 Metadata 目录

```
/mnt/ttlab-backups/
├── Daily/<机器名>/…            # 文件本体，结构不变
├── Checksums/<机器名>/…        # SHA-256 比对，格式不变
├── State/…                     # 增量记账，不变
├── Logs/<机器名>/…             # 运行日志，不变
└── Metadata/<机器名>/          # ← 本阶段新增
        <时间戳>_SMB_Metadata.csv
```

### 4.3 字段定义

CSV 采用 UTF-8 with BOM（与 `Checksums/` 一致，便于 Excel 直接打开）。

| 字段 | 说明 |
|---|---|
| `relative_path` | 相对源挂载点的路径，与 Compare CSV 的 `Relative_Path` 同义 |
| `source_path` | 完整源路径（含挂载点），标明取自 D 盘原始位置还是 E 盘现用目录 |
| `file_name` | 文件名 |
| `file_size` | 字节数 |
| `creation_time_original` | **源端原始创建时间**，ISO-8601 带时区 |
| `modified_time_original` | 源端修改时间，ISO-8601 带时区 |
| `access_time_original` | 源端访问时间，ISO-8601 带时区 |
| `change_time_original` | 源端变更时间（`stat` 语义，见 §2.3 可靠性说明） |
| `metadata_source` | 取值来源标识，如 `xattr:user.cifs.creationtime+stat` / `stat-only`（xattr 不可用时） |
| `metadata_collected_at` | 采集时刻，ISO-8601 带时区 |
| `collector_version` | 采集器版本，如 `smb_metadata v1.0.0` |
| `machine_name` | 机器名，如 `C4V61257XH_ViCell` |

**与 Checksums 的关联键**：`relative_path` + `source_path` + `file_size`。
通过该键可取到同一文件的 `Local_SHA256` / `NAS_SHA256` / `match_status`。

时间一律 ISO-8601 带时区（如 `2026-06-23T15:38:03.066743+08:00`），
不使用无时区的本地时间字符串（这同时部分改善审计发现 MD-013）。

---

## 5. 实现约束（不可违反）

1. **不改变现有复制逻辑**：`read_source_stable` → `write_atomic` → 回读校验，一行不动。
2. **不改变 SHA-256 流程**：源侧对内存字节计算、归档侧回读重算、比对与失败处置，一行不动。
3. **不改变 NAS 目录结构**：`Daily/` 下布局不变。
4. **不引入数据库**：本阶段输出仍为文件。
5. **不删除现有 CSV / JSON / LOG**。
6. **向后兼容**：采集器可通过环境变量关闭（`VICELL_COLLECT_METADATA=0`），
   关闭后程序行为与整改前完全一致。
7. **metadata 采集失败绝不阻断备份**：
   - 任何异常（xattr 不支持、无数据、权限、I/O）均被捕获；
   - 文件**照常归档**，SHA-256 校验流程不受影响；
   - 失败以 **WARNING** 记录，并在运行结束时给出**汇总统计**
     （避免 13 万个文件产生 13 万条日志）；
   - 采集失败时仍写出该行，`metadata_source` 标为 `stat-only` 或 `failed`，
     缺失字段留空——**不留空白行，让"采集失败"这件事本身也有记录**。

---

## 6. 风险等级说明（审计观点保留）

> 以下观点来自 `AUDIT-2026-08-03-data-integrity.md`，须在整改后保留，不得因整改而淡化。

**MD-001 并不是因为文件复制失败。**

文件字节内容完整、SHA-256 双向校验全部通过、归档副本可用。
真实情况是：**源端 metadata 可获取，但原方案没有采集。**

**整改后的风险变化：**

| 范围 | 整改后风险 | 说明 |
|---|---|---|
| **新产生的数据** | **降低**（High → Low） | 创建时间等元数据随归档同步采集并留证。残留风险：NAS 副本自身不携带该字段，属技术限制，已在 §3 明确说明 |
| **历史归档数据** | **需单独评估** | 整改前已归档的文件，其元数据当时未采集。是否可补采取决于**源端文件是否仍存在**：<br>① 源端仍在 → 可运行 `--metadata-backfill` 补采，但补采时刻晚于归档时刻，须在记录中体现<br>② 源端已删除 → **永久不可恢复**（本项目已知至少 3 个样品属此情形） |

**历史数据评估要点**：
- 补采得到的 `creation_time_original` 是**补采当时源端的值**，不是归档当时的值。
  若源端文件在归档后被替换过，两者会不一致——而这恰恰只有 SHA-256 能发现。
  因此补采记录必须与 Checksums 记录联合解读，不可单独作为证据。
- `metadata_collected_at` 字段的存在正是为此：它让"何时采集"这件事本身可被审查。

---

## 7. 后续阶段（本阶段不做，登记备查）

| 阶段 | 内容 | 对应审计项 |
|---|---|---|
| 二 | PostgreSQL 元数据库，Metadata CSV 降级为导出物 | MD-002 / MD-007 / MD-008 |
| 三 | 恢复验证制度与 `restore_drill` 记录 | MD-003 |
| — | 告警通道打通、心跳巡检 | MD-004 / MD-005（**优先级高于本阶段，可并行**） |
| — | FLEX2 同步本采集器 | MD-009 一致性 |
| — | 属主/ACL 是否采集 | 待 QA 判定 |
