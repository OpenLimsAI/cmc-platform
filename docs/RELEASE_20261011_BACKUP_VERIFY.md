# MDM逐份恢复验证发布记录

> 日期：2026-10-11｜状态：P16已明确确认；代码/本地与Linux合成隔离验证通过，正式验证服务、已有真实备份与看板更新正在发布验收。不得将下一次自然每日链路标为已通过。

## 范围与版本

仅修改cmab-mdm-platform备份配套和cmc-platform-monitor报告读取/展示；不改物料/设备/登录业务，不对Mac库或Linux原生数据库执行恢复。无新数据库迁移，不改变每日02:00备份timer、07:00兜底、Hub路径/端口和管理员权限。用户明确确认本次两仓修改、测试及Linux发布。

- MDM实现提交：a404181f3634d21f93029db27f0031ff77d8c6ac；pending摘要/队列发布顺序另有修复，最终SHA待本节验收记录。
- monitor最终代码/文档SHA在Git日志及下方实际验收登记。
- 官方镜像：postgres:16.15-bookworm（linux/amd64）；仓库摘要sha256:0ea6700a3b4f0ae6ce746519073558aed4d88a79d8d07622a9a644946c7319c4；实际运行内容ID sha256:ec9f656f17c8b4dfebf49e58cf5c46d493d4846d4ea6d8b85d0637f68ee33bfc。
- Linux直连DockerHub超时，改由Mac下载官方amd64镜像、导出指定平台后传至Linux。镜像归档SHA256 46aacaaa1883767960d30b76121868193b55281b409a9abc005e82dd9cc9e8c9，两端一致，Linux载入身份/平台一致。镜像约157MB；不通过文件复制发布项目代码。

## 实现与权限

MDM每日service显式开启BACKUP_VERIFY_ENABLED；普通手工/发布保护性备份默认关闭。现有cmab_app在只读一致性snapshot中取得应用38张表的清单、计数、结构、版本、扩展等基线；pg_dump使用同一snapshot。只读核验该账号可覆盖当前范围且无coverage_gaps，当前大对象0个；无需扩大pg_largeobject权限。无法取得基线时保留普通备份并显式缺口。

产物身份绑定basename/字节数/mtime/SHA/源InvocationID/开始结束。MDM先原子发布pending摘要再发布请求，防止快速执行后的终态被pending覆盖；systemd path触发独立串行验证service，不依赖网页。全恢复严格错误退出，同snapshot对账；1CPU/512MiB/600秒、network=none、不发布端口，不挂正式数据目录/配置/Docker socket。仅按唯一标签+ID清理本次容器/专用匿名卷，ExecStopPost覆盖异常停机清理；不全局prune。

完整报告root私有在/var/lib/cmab-mdm-backup-verify/reports，请求目录prometheus私有；脱敏摘要在/var/lib/cmc-platform-monitor/mdm-verification，prometheus属主、opsmonitor-evidence组只读。看板不读dump、不计算其SHA、不获得Docker控制或MDM源库账号；已有JSONB保存最小报告。报告90天、dump原30天，侧基线随dump保留期清理。

restore/integrity/cleanup与备份执行分开。失败红色、未完成/缺基线黄色、不可读/错配灰色；只有本份必要检查通过且清理正常才能绿。单库结构/数据验证排除对象所有者/ACL、服务器级角色口令、业务网站端到端、异地/外部文件、并发序列当前值和业务内容真实性判断。

## 已完成检查

- monitor后端60项通过（既有httpx/Starlette弃用提示1项）；前端3项、TypeScript/Vite构建通过，新JS index-osVqnXlR.js。
- 离线MDM配套11项通过，所有Docker/SQL均桩；覆盖损坏身份、对账差异、失败/超时、隔离参数、缺基线、清理与报告范围。新增monitor7项包含错配、不可读、未来证据、验证失败不改备份成功、缺基线不绿。
- Linux真实合成Docker检查：源备份期间2行→3行，同snapshot dump/恢复仍为2行；全恢复+基线检查通过，计数错配和无效archive分别检测失败，测试后验证容器0个。成功一次5.067秒，恢复库约8MB、临时数据目录48,281,024字节、结束时内存样本37.33MiB/512MiB；该样本不代表运行峰值或真实MDM耗时。
- MDM a404181已按现有deploy/deploy.sh发布，保护性备份在backups/releases/linux-20261011T044029Z.XKgV5S/database；迁移链核验、设备/物料前后计数相同，后端和nginx恢复active、Hub健康与在用首页核验通过。未产生新迁移；服务重启期间短暂502后恢复。

## 正式验证与剩余验收

正式验证服务/path安装、最终两仓同SHA、已有真实备份恢复/资源/清理、专用身份报告读取及Hub在用构建/API验收待下方补记。下一次自然每日备份才能确认生产同snapshot生成→path触发→恢复/对账→两次结束通知→看板结果的完整链路；不主动跑每日正式备份制造验收。

## 回滚

停止/禁用cmab-mdm-backup-verify.path，不动cmab-mdm-backup.timer；移除60-backup-verification.conf后daemon-reload即可恢复原普通备份路径。正在执行的验证经service停止及ExecStopPost清理自己的临时容器，保留dump和已有报告，不恢复或清空正式库。monitor可回到此前固定代码提交并重建/重启，既有4表和历史保留，无数据库downgrade。
