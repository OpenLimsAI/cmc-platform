# 本地测试环境说明

在**任意有 Docker 的机器上**（Mac / Linux）运行回归测试，**不需要实验室网络**。

```bash
bash tests/local_cifs_suite.sh
```

约 1 分钟，输出 12 项断言的通过/失败与总结，退出码 0/1。

---

## 它是怎么搭的

```
Samba 容器（dperson/samba）
  ├── 共享 instrument  只读   ← 模拟仪器工作站的导出目录
  └── 共享 nas         可写   ← 模拟 NAS 归档区
        ↑ 真 CIFS 挂载（vers=3.0）
  特权容器 python:3.11-slim  ← 跑 vicell_ingest.py / heartbeat_check.py
```

**用的是真 CIFS 协议栈**，不是 tmpfs 模拟。所以扩展属性、挂载语义、
只读挂载行为这些都能真实覆盖。

---

## ✅ 能覆盖什么

| 覆盖项 | 说明 |
|---|---|
| 只读源自验 | 源挂载点可写即中止（铁律 2） |
| 完整采集流程 | Data / Export / Images 三类，文件数与内容 |
| SHA-256 双向校验 | 比对表 `match_status` 全 `MATCH` |
| **Windows 创建时间采集** | `user.cifs.creationtime` 在本地 Samba 上**同样可读**，metadata 采集器可回归 |
| 归档副本保留源修改时间 | |
| 幂等性 | 二次运行新增 0 |
| 源端删除检测 | 删除后只报告、不删归档 |
| **NAS 不可写** | 退出码 1 + **本地兜底告警仍生成** |
| 心跳字段与状态 | 字段完整性、`SUCCESS`/`FAILED` |
| 心跳巡检 | 新鲜 → 0；陈旧 → 1 |
| 告警分类与限流 | 见 `vicell/alerting.py` 的 `__main__` 自检 |

---

## ❌ 不能覆盖什么（重要）

### 1. 生产 NAS 的具体实现行为 —— 已有血的教训

**本地 Samba 的 `rename` 不会重置 mtime，生产 NAS 会。**

实测对比（2026-08-03）：

| 环境 | `utime` 设为 2025-06-15 后 `rename`，mtime 变成 |
|---|---|
| 生产 NAS（`//10.0.6.100/ttlab_backups`） | **归档当时的时间**（被重置） |
| 本地 Samba | 2025-06-15（保留） |

**后果**：v1.2.0 那个"先 `utime` 再 `rename`"的 bug，**在本地测试里会顺利通过**，
然后带着错误的时间戳上生产。该 bug 是在真实 NAS 上抽查才发现的。

> **结论：凡是涉及 NAS 或仪器侧具体实现行为的结论，本地通过不等于生产可用，
> 必须在真实环境复验。** 本地套件的定位是**回归测试**（防止改坏已有功能），
> 不是**验收测试**。

### 2. 真实仪器与真实数据

- Vi-CELL 工作站是 **Win7 + SMB 2.1**；本地 Samba 跑的是 SMB 3.0
- 真实数据的结构怪癖（多行宽 CSV、混合命名、目录 mtime 被搬迁刷掉等）无法模拟
- 真实的吞吐与延迟特性（仪器侧 15 MB/s 上限、并发无收益）无法模拟

### 3. 生产环境的权限与属主

归档区属主是 `flex2ingest`、NAS 以固定 `uid/gid/file_mode` 挂载——
这些配置类问题只能在真实环境暴露（首跑那次 `Permission denied` 就是）。

---

## 环境坑（踩过，别再踩）

**Samba 的后端存储必须用 Docker 卷，不能用 macOS 主机目录 bind mount。**

Docker Desktop 的主机文件共享层不支持 SMB 需要的 rename 语义，
会让 `os.replace` 报 `[Errno 95] Operation not supported`，
产生与产品完全无关的假失败。套件已改用 `docker volume`，数据留在 Linux 虚拟机的 ext4 上。

**比对 CSV 是 CRLF 行尾**（`csv.writer` 写出），
用 awk 比较最后一列前必须 `tr -d '\r'`，否则 `$NF` 是 `MATCH\r` 而不是 `MATCH`。

**需要 `--privileged`** 才能在容器内挂载 CIFS。

---

## 什么时候该跑

| 场景 | 跑本地套件 | 还需真实环境验证 |
|---|---|---|
| 改了告警 / 心跳 / metadata 逻辑 | ✅ 必跑 | 部署后跑一次真实增量即可 |
| 改了复制 / 校验 / 时间戳处理 | ✅ 必跑 | **必须**在真实 NAS 复验（见上文 rename 教训） |
| 改了挂载参数 / 权限 / 部署配置 | 参考价值有限 | **只能**在真实环境验证 |
| 接入新仪器 | ✅ 可先跑通流程 | 数据源勘察与首跑必须在真实环境 |
