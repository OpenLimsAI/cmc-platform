# MDM逐份恢复验证发布记录

> 日期：2026-10-12更新｜状态：P16已上线；首次自然备份的等价约束误报已修复，同文件新ID复验13项检查通过，看板已绿。下一次新产物自然任务尚待观察。

## 范围与版本

仅修改cmab-mdm-platform备份配套和cmc-platform-monitor报告读取/展示；不改物料/设备/登录业务，不对Mac库或Linux原生数据库执行恢复。无新数据库迁移，不改变每日02:00备份timer、07:00兜底、Hub路径/端口和管理员权限。用户明确确认本次两仓修改、测试及Linux发布。

- MDM实现提交：a404181f3634d21f93029db27f0031ff77d8c6ac；后续修正pending发布顺序及私有诊断/代码版本追溯，最终MDM SHA 389fd5918b373f45cbbc956f4397176e37ed2d29，Mac/GitHub/Linux相同。
- monitor基础实现a3b8453448302743422806bf3daeb877be9ef5b6；最终业务代码SHA c23132b8f2664b0e6dc41d5401f682cd98b8313f，必要检查完整清单与资源摘要已补齐并部署，Mac/GitHub/Linux相同。后续仅更新本发布记录，不需重启业务服务。
- 官方镜像：postgres:16.15-bookworm（linux/amd64）；仓库摘要sha256:0ea6700a3b4f0ae6ce746519073558aed4d88a79d8d07622a9a644946c7319c4；实际运行内容ID sha256:ec9f656f17c8b4dfebf49e58cf5c46d493d4846d4ea6d8b85d0637f68ee33bfc。
- Linux直连DockerHub超时，改由Mac下载官方amd64镜像、导出指定平台后传至Linux。镜像归档SHA256 46aacaaa1883767960d30b76121868193b55281b409a9abc005e82dd9cc9e8c9，两端一致，Linux载入身份/平台一致。镜像约157MB；不通过文件复制发布项目代码。

## 实现与权限

MDM每日service显式开启BACKUP_VERIFY_ENABLED；普通手工/发布保护性备份默认关闭。现有cmab_app在只读一致性snapshot中取得应用38张表的清单、计数、结构、版本、扩展等基线；pg_dump使用同一snapshot。只读核验该账号可覆盖当前范围且无coverage_gaps，当前大对象0个；无需扩大pg_largeobject权限。无法取得基线时保留普通备份并显式缺口。

产物身份绑定basename/字节数/mtime/SHA/源InvocationID/开始结束。MDM先原子发布pending摘要再发布请求，防止快速执行后的终态被pending覆盖；systemd path触发独立串行验证service，不依赖网页。全恢复严格错误退出，同snapshot对账；1CPU/512MiB/600秒、network=none、不发布端口，不挂正式数据目录/配置/Docker socket。仅按唯一标签+ID清理本次容器/专用匿名卷，ExecStopPost覆盖异常停机清理；不全局prune。

完整报告root私有在/var/lib/cmab-mdm-backup-verify/reports，请求目录prometheus私有；脱敏摘要在/var/lib/cmc-platform-monitor/mdm-verification，prometheus属主、opsmonitor-evidence组只读。看板不读dump、不计算其SHA、不获得Docker控制或MDM源库账号；已有JSONB保存最小报告。报告90天、dump原30天，侧基线随dump保留期清理。

restore/integrity/cleanup与备份执行分开。失败红色、未完成/缺基线黄色、不可读/错配灰色；只有本份必要检查通过且清理正常才能绿。单库结构/数据验证排除对象所有者/ACL、服务器级角色口令、业务网站端到端、异地/外部文件、并发序列当前值和业务内容真实性判断。

## 已完成检查

- monitor后端61项通过（既有httpx/Starlette弃用提示1项）；前端3项、TypeScript/Vite构建通过，新JS index-osVqnXlR.js。
- 离线MDM配套11项通过，所有Docker/SQL均桩；覆盖损坏身份、对账差异、失败/超时、隔离参数、缺基线、清理与报告范围。新增monitor8项包含错配、不可读、未来证据、验证失败不改备份成功、缺基线不绿。
- Linux真实合成Docker检查：源备份期间2行→3行，同snapshot dump/恢复仍为2行；全恢复+基线检查通过，计数错配和无效archive分别检测失败，测试后验证容器0个。成功一次5.067秒，恢复库约8MB、临时数据目录48,281,024字节、结束时内存样本37.33MiB/512MiB；该样本不代表运行峰值或真实MDM耗时。
- MDM a404181已按现有deploy/deploy.sh发布，保护性备份在backups/releases/linux-20261011T044029Z.XKgV5S/database；迁移链核验、设备/物料前后计数相同，后端和nginx恢复active、Hub健康与在用首页核验通过。未产生新迁移；服务重启期间短暂502后恢复。

## 正式验证与剩余验收

正式验证服务/path已安装且path启用；原备份timer继续active，02:00及最多5分钟随机延迟不变。最新已有备份cmab_mdm_prometheus_20261010_1803.dump（本地2026-10-11 02:03:44，1,007,665字节，SHA256 f69070498b1b54760abdbea5ed6bb91948f4c9e8ca6d82c524c57b33a8cd512d）已通过实际完整恢复，验证ID 460f8b3018c042cf87f8bcc2f73f2559，UTC04:45:02～04:45:11、耗时9.276秒。恢复库23,419,927字节，临时数据目录80,426,432字节，结束内存样本49.8MiB/512MiB（不是峰值），cleanup=passed且Docker容器0个。完整报告root600，摘要640/组只读；旧文件没有备份时基线，因此restore=verified、integrity=not_verified，看板黄色准确保留缺口。

最终reader UID995及服务实际组实测：摘要允许读取，dump内容、验证配置、私有完整报告与Docker socket均拒绝。collector已将该摘要追加持久化；Hub实际overview返回备份成功+恢复已验证+缺基线黄色，首页/JS与生产构建逐字节一致。未登录401、SYS_ADMIN200、DEPT_ADMIN403、临时密码403（服务器内短期合成token，不是用户真实MDM浏览器登录）；不打印口令/令牌。

最终MDM版本389fd59已按deploy/deploy.sh再次完整发布核验，报告backups/releases/linux-20261011T044956Z.eu1G1O，设备/物料计数一致、迁移版本仍0062、业务服务与nginx active。Mac仍为明确标注模拟，构建index-D_cw7FxI.js；Linux为生产index-osVqnXlR.js。最终复核两仓版本与origin/main一致，Linux工作区干净；cmab-backend/nginx、monitor API/collector、backup timer及verify.path均active，verify.service上次执行success后inactive正常；全部Docker容器0个。下一次timer当前计划为北京时间2026-10-12 02:03:17（02:00加随机延迟），自然每日备份才能确认生产同snapshot生成→path触发→恢复/对账→两次结束通知→看板结果的完整链路；不主动跑每日正式备份制造验收。

## 回滚

停止/禁用cmab-mdm-backup-verify.path，不动cmab-mdm-backup.timer；移除60-backup-verification.conf后daemon-reload即可恢复原普通备份路径。正在执行的验证经service停止及ExecStopPost清理自己的临时容器，保留dump和已有报告，不恢复或清空正式库。monitor可回到此前固定代码提交并重建/重启，既有4表和历史保留，无数据库downgrade。

## 2026-10-12 首次自然每日链路只读调查

用户反馈MDM红色卡片。实际backup.service在北京时间02:03:40～02:03:42退出0，生成cmab_mdm_prometheus_20261011_1803.dump（1,010,258字节），当前SHA256与报告一致：1f2af5bfd5a19983a21e31af1da5cb8b6b810d6a899e25899563adaef2a20c8f。verify.path自然触发02:03:42～02:03:54，验证ID b4815e723fa34b5b9c5899dafef45d73，restore=verified、full_restore=passed、38张表计数完全一致，清理passed且无验证容器残留；验证业务结果failed、failure_step=baseline_compare。worker退出0仅表示请求已处理，不能替代报告内验证结果。

唯一不一致项constraints：源/恢复均180条约束，14条CHECK定义不同。源写法为常量varchar数组整体转text[]，恢复后变成各常量先转text再组数组；逐条只读核验约束身份/类型/验证标识及所有允许值均相同，14条差异完全是这一个类型转换表达式重写，其他catalog字段/表计数均相等，coverage_gaps为空。源PG16.15 Ubuntu、隔离目标PG16.15 Debian；不能归因于主版本不匹配。现有验证器直接比较pg_get_constraintdef文本，把恢复重解析产生的等价写法当结构变化，属于本次误报。原失败报告保留，不直接改成passed。

自然任务→同snapshot基线→恢复→清理→报告→看板的触发链路已有实际证据，但完整验收未通过；待修正等价约束比较，并用此类varchar数组约束及真实不等价变更补回归后复验，不能跳过约束检查。此轮只读读取API/报告/备份清单与SHA，未修改MDM/monitor业务代码、数据库/权限/调度，未启动备份/恢复、创建容器或部署。MDM当前SHA ef0373adbd0da1816807f8b2cacf7dec7a01c58a、monitor8064e1edac79bd090f78a9fa2f25c33ea55a611b；服务active。

## 2026-10-12 等价约束修正发布与同文件复验

用户确认修复后，MDM实现仅接受已核实的常量varchar数组转text等价CHECK写法，并按SQL词法保留字符串/引号标识符；约束清单、身份/类型/验证标志及真实规则变化仍严格比较。普通每日入队行为保持，显式enqueue --reverify生成新验证ID，在私有请求记录原验证ID，原基线和失败报告不改写。策略标识literal_varchar_array_to_text_v1写入验证报告，原始两份catalog继续保留。

本地20项离线配套测试通过，覆盖等价与真实允许值/运算符/字段/类型/NULL条件变化、缺失/属性变化、字符串里的SQL与转义、未知表达式，以及首次/复验ID和报告保留；所有SQL/Docker操作为桩。直接对本次报告180条真实约束回归，14处等价写法通过，逐处类型改变仍拒绝。Linux实际隔离合成源测试：并发新增后备份仍取原snapshot2行；历史等价约束通过，真允许值变更/计数差异/损坏archive均检出，容器清理完毕。未连接Mac或Linux原生库作合成测试目标。

MDM最终SHA b1d9d08a7c22ecaeb0e67745ccf2a7d7e95a71e0（包含416ff66修复），Mac→GitHub→Linux相同，按现有deploy/deploy.sh发布完成。保护性发布备份/验收目录/opt/cmab-mdm-platform/backups/releases/linux-20261012T013053Z.nzUhgk；现有迁移版本核验、设备/物料前后计数一致，服务和Hub验收恢复正常。无新迁移或权限/调度改变；部署短暂停后端期间502后按脚本恢复。

北京时间09:32对凌晨原文件cmab_mdm_prometheus_20261011_1803.dump显式复验，SHA仍1f2af5bfd5a19983a21e31af1da5cb8b6b810d6a899e25899563adaef2a20c8f。新验证ID0e64866ae5aa4d4dbeaf1e0793964c75引用原失败IDb4815e723fa34b5b9c5899dafef45d73；完整恢复+13项检查全部passed，restore/integrity均verified，耗时8.963秒、结束内存样本49.81MiB/512MiB（不是峰值）、临时数据80,426,432字节已清理，无验证容器残留。原失败报告SHA be050a682b135a47a233ea28092a24d658ffa4522b1a5f26a935f60336fb26bd及原基线SHA af038a778bd3fa149a790e9633161a74613cebda97a3344eb7dff27ae739a6fd均未变化。

恢复结束通知已自动驱动collector采集，UTC01:32:32.599362的Hub实际overview为绿色“备份完成，恢复验证通过”，关联本次新ID。未修改monitor业务判定或强制改历史状态；只同步本次文档/离线回归脚本，Mac模拟保持。每天02:00原备份及07:00兜底保持，10-12自然链路的等价误报已定位修复并在同文件实测通过；下一次10-13新产物自然执行尚未发生，不冒称已验收。
