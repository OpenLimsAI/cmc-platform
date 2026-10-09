# Linux运行与发布说明

> 版本：0.7｜日期：2026-10-09｜状态：现行操作手册；首次/级联发布过程移至日期化记录。

目标/opt/cmc-water-system-dashboard，prometheus；后端127.0.0.1:8015、nginx静态前端127.0.0.1:5115，用户经Hub /water/。2026-10-09已有服务发布记录；最近有证据的状态见 [STATUS](../../docs/STATUS.md)，本轮两页部署和远端核验结果见 [两页发布记录](../../docs/releases/20261009-two-page-linux.md)，首次/级联历史见 [历史发布记录](../../docs/releases/20261009-linux.md)。

## 发布前检查

核对有效授权、主机/实例、完整SHA、工作区、五表只读结构/授权/数据及角色配置；备份旧固定SHA、构建、保护配置与恢复步骤。源码通过同一GitHub仓库获取，不复制Mac业务数据/凭据。按 [docs/08](../../docs/08-development-deployment.md) 处理跨仓库/迁移边界。

应用只支持当前五表staging消费；虽然Mac/Linux均已有使用记录，受控快照/来源截止尚未实现（OP-06）。受限验证与正式用途分开，后者需完成真实身份、浏览器及用途所需治理条件。

## 首次配置与固定版本构建

仅第一次且backend/.env不存在时使用configure.sh。它复用本机已有QC lims_reader分析DSN和MDM HS256配置、要求实际Noto字体，并生成0600文件；不会输出秘密或覆盖现有.env。缺依赖、字体或算法条件时退出。RS256需安全配置JWT_VERIFY_KEY中的PEM，自动配置脚本不支持该转换。

Linux通过git pull --ff-only等所属流程取得目标完整SHA并核对后，在/opt/cmc-water-system-dashboard执行：

```bash
bash deploy/linux/configure.sh          # 仅首次，已有.env时不运行
bash deploy/linux/prepare.sh <完整40位SHA>
```

prepare只校验HEAD/干净工作区/.env并锁依赖构建，不拉代码或安装服务。正在升级时8015/5115属于既有服务；首次安装时须空闲，不能以“必须无监听”阻止正常升级。

## 安装/更新服务

```bash
bash deploy/linux/deploy.sh <完整40位SHA>
```

deploy会再执行prepare，检查APP_ENV非mac_dev、字体文件及http://127.0.0.1:5100/mdm/api/v1/health，备份并安装unit/nginx配置，nginx-t后enable/restart后端、health、reload nginx和静态页检查。

nginx-t失败会恢复本脚本改动的配置；应用启动/健康失败不会自动回退代码或构建。脚本不改Hub注册、不配置MDM角色、不查数据库完整业务对账，不能作为全部验收通过证明。静态构建不是原子切换；发布前单独保留旧构建/固定SHA以恢复。敏感备份保持0700/0600，执行构建前恢复umask 022；核对dist/index.html为0644、assets目录为0755，避免nginx无法读取。

## 运行、回滚与验收

```bash
systemctl status water-backend
journalctl -u water-backend
```

发布配置备份位于logs/deploy-日期时间，matplotlib缓存为logs/matplotlib。出现问题按预先核实方案回到同仓库旧固定SHA、重建并恢复服务配置，再验Hub资源/身份/数据；本次没有业务结构变更，不删/回写源结果。人员撤权走MDM流程，旧access到期窗口见docs/06。

每次发布执行 [docs/09](../../docs/09-test-acceptance.md) 的适用验收：资源/深链、真实身份/会话、独立只读对账、PNG中文、Excel原文、ZIP内容与实际下载。服务部署、数据到位、角色建立/人员授权、真实两档身份和浏览器分别登记；当前未完成项不能由Mac结果或匿名health替代。
