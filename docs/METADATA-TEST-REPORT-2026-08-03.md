# Metadata 采集器测试报告

| | |
|---|---|
| 测试日期 | 2026-08-03 |
| 被测对象 | `vicell/smb_metadata.py` v1.0.0 + `vicell/vicell_ingest.py` v1.3.0 |
| 对应整改项 | `AUDIT-2026-08-03-data-integrity.md` **MD-001** |
| 设计依据 | `docs/DATA_INTEGRITY_METADATA_DESIGN.md` |
| 测试环境 | Linux 172.19.0.105 → Win7 工作站 `C4V61257XH`（SMB 2.1）→ NAS `ttlab_backups` |
| 特殊说明 | 测试期间图片回补作业**并发运行**中，链路存在竞争。相关耗时数据已标注 |

**结论：三项测试全部通过。** 采集能力可用、性能可接受、失败时不阻断备份。

---

## 前置：改动范围核验

本阶段的硬约束是"不改变复制与校验逻辑"。用 diff 核验（非人工声明）：

```
$ git diff --stat HEAD -- vicell/
 vicell/vicell-ingest.env.example |   5 ++
 vicell/vicell_ingest.py          | 126 ++++++++++++++++++++++++++++++++++++---

$ git diff HEAD -- vicell/vicell_ingest.py | grep -E "^[-+].*(read_source_stable|sha256_file|hashlib.sha256|os.fsync|os.replace|os.utime|write_atomic\(dest)"
（无输出）
```

`read_source_stable` / `sha256_file` / `hashlib.sha256` / `os.fsync` / `os.replace` / `os.utime`
及 `write_atomic()` 调用**全部未出现在 diff 中**，即复制与校验路径一行未改。

改动仅落在四处：两个归档函数各追加一行 `mc.collect(...)`（位置在**归档成功并写入 state 之后**）、
`main()` 中创建采集器与写出、配置项与文档字符串。

`Checksums/` 的 9 列表头、`Daily/` 目录结构、state JSON 结构均未变动。

---

## Test 1 — 单文件 metadata 读取与交叉验证

**目的**：确认 `os.getxattr("user.cifs.creationtime")` 的解码结果与 SMB 协议原生查询一致。

**方法**：同一文件，分别用 `smbclient allinfo`（走 SMB 协议原生 QUERY_INFO）与本模块读取，逐字段比对。

**结果**

被测文件 `//10.0.13.36/Vi-Cell$/Data/0005m10.txt`：

| 字段 | A：`smbclient allinfo` | B：本模块（`getxattr` + `stat`） | 一致 |
|---|---|---|---|
| create_time | `Thu Jul 2 09:34:05 PM 2026` | `2026-07-02T21:34:04.867085+08:00` | ✅ |
| access_time | `Thu Jul 2 09:34:05 PM 2026` | `2026-07-02T21:34:04.867085+08:00` | ✅ |
| write_time | `Tue Jun 23 03:38:03 PM 2026` | `2026-06-23T15:38:03.051143+08:00` | ✅ |
| change_time | `Thu Jul 2 09:34:11 PM 2026` | `2026-07-02T21:34:10.904324+08:00` | ✅ |

第二个被测文件 `//10.0.13.36/VC-DImg$/0005m10/0005m10_10.tif`（D 盘原始位置）：

| 字段 | 值 |
|---|---|
| creation_time | `2026-06-23T15:38:03.066742+08:00` |
| modified_time | `2026-06-23T15:38:03.066743+08:00` |

**判定：通过。** 四个时间字段全部吻合（`allinfo` 取整到秒，本模块保留亚秒精度）。
本模块输出为 ISO-8601 带时区。

**附带确认**：`st_atime` 与 `st_ctime` 在本环境下确实映射自 SMB 的 `AccessTime` 与 `ChangeTime`
（见上表），故设计文档 §2.3 中"照实采集并标注来源"的处理方式成立。

---

## Test 2 — 批量采集（生产数据）

**目的**：在真实规模下统计采集成功率与耗时。

**方法**：对**已归档**的全部文件执行 `--metadata-backfill`（只读源端，不复制、不写 state、
不触碰归档区）。执行期间图片回补作业并发运行。

**结果**

| 项 | 数值 |
|---|---|
| total files | **115 384** |
| metadata success（完整，含创建时间） | **115 384** |
| metadata partial（仅 stat） | 0 |
| metadata failed | **0** |
| **成功率** | **100.0%** |
| 耗时 | 8 分 17 秒（20:44:02 → 20:52:19） |
| 平均 | **4.3 ms/文件**（并发负载下；空闲时实测 2.6 ms/文件） |
| 输出 | `Metadata/C4V61257XH_ViCell/20260803_204402_SMB_Metadata.csv`，115 384 行 / 41 MB |

`metadata_source` 分布：`xattr:user.cifs.creationtime+stat` **115 384 条（100%）**。

**产出抽样核验**

```
D 盘原始位置的图片：
  路径: /mnt/vicell-old/dimg/0005m10/0005m10_1.tif
  创建: 2026-06-23T15:38:03.051144+08:00     ← 与拍摄时间一致（原件）
  修改: 2026-06-23T15:38:03.051143+08:00

E 盘现用目录的文本：
  路径: /mnt/vicell/Data/0005m10.txt
  创建: 2026-07-02T21:34:04.867085+08:00     ← 搬文件夹当天（副本）
  修改: 2026-06-23T15:38:03.051143+08:00     ← 原始写入时间
```

**关键量化：创建时间与修改时间不同的文件占 55 526 / 115 384 = 48.1%。**

这直接证明创建时间**不是冗余字段**——对近一半的归档文件，它承载着修改时间无法提供的独立信息
（本例中即"原件 vs 人工副本"的区分）。整改前这部分信息 100% 丢失。

**判定：通过。**

---

## Test 3 — metadata 读取失败场景

**目的**：确认采集失败时备份继续执行、文件正常归档、失败以 WARNING 记录。

**方法**：构造隔离的失败环境，避免污染生产数据——

- 机器名改为 `ZZTEST_ViCell`，使 state / Checksums / Metadata / Logs / Daily 全部落在独立路径；
- 源端使用 **tmpfs 挂载**（`/mnt/zztest`）。tmpfs 不支持 `user.*` 扩展属性，
  `getxattr` 必然失败——这是真实的失败条件，不是模拟或打桩；
- 历史源与配置源指向不存在的路径，验证跳过逻辑。

预置失败条件确认：

```
xattr 支持情况: OSError[61] No data available
```

**结果**

```
Data   : 新增 2  跳过 0  变化 0  失败 0
Export : 新增 1  跳过 0  变化 0  失败 0
Images : 新增目录 1  跳过目录 0  文件 3  失败 0
Metadata: 采集 6  完整 0  仅stat 6  失败 0
WARNING | Metadata 采集不完整（6 个文件）: 创建时间不可得（user.cifs.creationtime 无值或不支持）；样例: /mnt/zztest/Data/a.txt
INFO    | Metadata 已写出（6 行）
INFO    | 完成
```

| 验证点 | 结果 |
|---|---|
| 备份是否继续执行 | ✅ 全部 6 个文件正常归档，退出状态"完成" |
| SHA-256 校验是否受影响 | ✅ 比对表 6 行**全部 `MATCH`** |
| 是否记录 WARNING | ✅ 已记录，且**按原因聚合为 1 条**（6 个文件未产生 6 条日志） |
| 失败是否仍留痕 | ✅ CSV 仍写出 6 行，`creation_time_original` 留空，`metadata_source` = `stat-only` |
| 是否抛出异常 | ✅ 无 |

CSV 实际内容（节选）：

```
Data/a.txt,/mnt/zztest/Data/a.txt,a.txt,8,,2026-08-03T20:43:18.796148+08:00,...,stat-only,...
                                        ↑ 创建时间留空                        ↑ 来源标注
```

**判定：通过。** 采集失败被完整降级处理：不抛异常、不阻断、有告警、有留痕。

**附带发现**：首次尝试用 bind mount 构造失败环境时，程序预检报"源未挂载"并中止
——因为 `os.path.ismount()` 对同设备 bind mount 判定为 false。这**验证了预检逻辑是有效的**
（宁可停也不在结构异常时继续），随后改用 tmpfs 完成测试。

**测试残留清理**：`Daily/ZZTEST_ViCell`、`Checksums/ZZTEST_ViCell`、`Metadata/ZZTEST_ViCell`、
`Logs/ZZTEST_ViCell`、`State/ZZTEST_ViCell_backup_state.json` 及 tmpfs 挂载均已删除，
NAS 上残留检查为 0。

---

## 性能小结与运行建议

| 场景 | 实测 | 说明 |
|---|---|---|
| 空闲时单文件 | 2.6 ms | 冷读，未命中客户端缓存 |
| 并发负载下 | 4.3 ms | 与图片回补争抢同一条 15 MB/s 链路 |
| 嵌入日常归档 | 每样品目录 +0.13 s | 相对复制耗时 8 s/目录，占比约 1.6%，可忽略 |
| 全量补采 13 万文件 | 约 8–10 分钟 | 建议安排在归档作业空闲时段 |

**对照方案**（不采用，仅作记录）：`smbclient allinfo` 批量调用边际 72 ms/文件，
13 万文件需约 2.6 小时，且需引入外部命令依赖。

---

## 遗留与后续

1. **`--metadata-backfill` 缺少进度输出**。本次运行 8 分钟内无任何中间日志，
   期间需通过 `/proc/<pid>/io` 才能判断是否在推进。建议后续加入周期性进度行。
   （不影响正确性，不阻塞本阶段交付。）
2. **历史归档数据的补采时效性**：本次补采覆盖的是**补采当时源端仍存在**的文件。
   源端已删除者（本项目已知至少 3 个样品）**永久不可恢复**，见设计文档 §6。
3. **FLEX2 尚未接入本采集器**，其归档目前仍无原始 metadata。属 MD-009 一致性问题，
   建议同步实施。
4. 属主 / ACL（`system.cifs_ntsd`，201 ms/文件）与 NTFS 属性本阶段未采集，
   待 QA 判定是否必需。

---

## 审计观点保留

> 以下为 `AUDIT-2026-08-03-data-integrity.md` 的原始判断，整改后仍然成立，不因整改而淡化。

**MD-001 并不是因为文件复制失败。** 文件字节完整、SHA-256 双向校验全部通过。
真实情况是：**源端 metadata 可获取，但原方案没有采集。**

整改后：

- **新产生的数据**：风险由 High 降至 Low。残留风险为"NAS 副本自身不携带 Windows 创建时间"
  ——属 Linux 技术限制，已在设计文档 §3 明确记载与解释口径。
- **历史归档数据**：**需单独评估**。可补采部分已于本次 Test 2 覆盖（115 384 个文件），
  但补采时刻晚于归档时刻，由 `metadata_collected_at` 字段体现，
  解读时必须与 `Checksums/` 记录联合使用，不可单独作为证据。
