# CMC Platform

本仓库汇集 10 个 CMC/CMAB 项目的代码与 Git 历史。各项目放在同名子目录中，保留各项目文件内容（MDM 的凭据清理例外见下文）；这次整合不代表已完成业务功能、启动方式或部署的运行时集成。

## 项目与导入版本

| 目录 | 来源仓库 | 导入提交（main） |
|---|---|---|
| `cmc-instrument-ingest/` | [qingcheng81/cmc-instrument-ingest](https://github.com/qingcheng81/cmc-instrument-ingest) | [`2de8f8330d69ba8fa8273eef3be03a487eb7ef92`](https://github.com/qingcheng81/cmc-instrument-ingest/commit/2de8f8330d69ba8fa8273eef3be03a487eb7ef92) |
| `cmc-labops/` | [qingcheng81/cmc-labops](https://github.com/qingcheng81/cmc-labops) | [`3ac2fb181cc57ed007dedcc585b310cc734899af`](https://github.com/qingcheng81/cmc-labops/commit/3ac2fb181cc57ed007dedcc585b310cc734899af) |
| `cmc-platform-monitor/` | [qingcheng81/cmc-platform-monitor](https://github.com/qingcheng81/cmc-platform-monitor) | [`85dda2e2365104c2d6f4658ff81d96ce8fac20dd`](https://github.com/qingcheng81/cmc-platform-monitor/commit/85dda2e2365104c2d6f4658ff81d96ce8fac20dd) |
| `cmc-quality-analytics-platform/` | [qingcheng81/cmc-quality-analytics-platform](https://github.com/qingcheng81/cmc-quality-analytics-platform) | [`9a5af3ded7e0e7cf398188b8dd14fdce262f8b9f`](https://github.com/qingcheng81/cmc-quality-analytics-platform/commit/9a5af3ded7e0e7cf398188b8dd14fdce262f8b9f) |
| `cmc-rd-lims-dashboard/` | [qingcheng81/cmc-rd-lims-dashboard](https://github.com/qingcheng81/cmc-rd-lims-dashboard) | [`179f08998af748d2a49681cb2c650ed44345d7cf`](https://github.com/qingcheng81/cmc-rd-lims-dashboard/commit/179f08998af748d2a49681cb2c650ed44345d7cf) |
| `cmc-rd-usp-dashboard/` | [qingcheng81/cmc-rd-usp-dashboard](https://github.com/qingcheng81/cmc-rd-usp-dashboard) | [`3a7bcb36ddbd50ebf6048c9fad3412f95d788384`](https://github.com/qingcheng81/cmc-rd-usp-dashboard/commit/3a7bcb36ddbd50ebf6048c9fad3412f95d788384) |
| `cmc-schema-migrations/` | [qingcheng81/cmc-schema-migrations](https://github.com/qingcheng81/cmc-schema-migrations) | [`7a6785a68b18c412c0dc10df97b1a8b709748457`](https://github.com/qingcheng81/cmc-schema-migrations/commit/7a6785a68b18c412c0dc10df97b1a8b709748457) |
| `cmc-water-system-dashboard/` | [qingcheng81/cmc-water-system-dashboard](https://github.com/qingcheng81/cmc-water-system-dashboard) | [`f4e2c81da2e56f7c52c040e8abbcc9c25c45ee25`](https://github.com/qingcheng81/cmc-water-system-dashboard/commit/f4e2c81da2e56f7c52c040e8abbcc9c25c45ee25) |
| `cmab-mdm-platform/` | [qingcheng81/cmab-mdm-platform](https://github.com/qingcheng81/cmab-mdm-platform) | [`5835e5b418b8ded4aee895466942122ac00a170b`](https://github.com/OpenLimsAI/cmc-platform/commit/5835e5b418b8ded4aee895466942122ac00a170b)（清理后的 main） |
| `cmab-hub/` | [qingcheng81/cmab-hub](https://github.com/qingcheng81/cmab-hub) | [`643ea6431b3acb91dbf94251f3c989572f774807`](https://github.com/qingcheng81/cmab-hub/commit/643ea6431b3acb91dbf94251f3c989572f774807) |

## 历史、分支与标签

既有八项目的原始提交不改写。整合主分支的初始提交以 8 个源 main 提交作为父提交，并将各项目的原始文件树放入对应子目录。原历史中的文件路径仍位于各自仓库根目录。

- 原分支保留为 `source/<项目名>/<原分支名>`，既有八项目及 Hub 分支指向原始提交；MDM 分支指向凭据清理后的对应提交。
- 原标签保留为 `source/<项目名>/<原标签名>`，保留原标签对象。
- 历史导入来源为 GitHub 已提交的分支和标签。MDM 另纳入负责人明确批准的 README 六行工作区更新，单独提交；没有其他未提交代码更新。
- Issues、Pull Requests、Actions secrets、运行记录等非 Git 数据未复制。

## 后续开发

在本仓库工作副本的对应项目子目录中开发，通过本仓库 main 或新功能分支提交。个人原仓库保留，本次不设置向原仓库的自动同步。旧项目目录及其 origin 不变。

`cmc-cost-modeler` 和原 code/archive 中的项目不属于本仓库。

## MDM 补充导入（2026-10-26）

MDM 原 main 为 `b8b422af82c0adbe86912a13c685a938743b6b89`。负责人批准只在迁移副本中清除明文运行凭据及种子账号默认密码，并同步清理相关历史；原目录、原仓库与原始历史不动。清理后的 main 为 `5835e5b418b8ded4aee895466942122ac00a170b`，保留全部 135 条提交的作者、时间、消息及非敏感内容，提交 SHA 因清理而改变。补充整合提交以既有 monorepo main 和清理后的 MDM main 为父提交。

源 main 没有额外分支或标签。MDM 的 `source/cmab-mdm-platform/main` 只保存清理后的历史；未导入原始敏感引用、替换引用或旧对象。代码中的 `__REDACTED_*__` 是清理占位符，运行前须按项目方式提供本地独立配置，不能把占位符当作可用凭据。

负责人另行批准的源 README 六行记录在历史导入之后单独提交。两份 `outputs/20260922-equipment-reload/` 设备 Excel 不复制、不加入 Git；源文件原样保留。`.env`、JWT 文件、数据库备份、依赖和构建产物也未复制。

本次只整合代码及清理后的 Git 历史，不迁移数据库、不改运行路径、不停止服务、不归档原目录、不部署。既有八项目的文件树与历史引用保持不变。

## Hub 补充导入（2026-10-26）

统一门户 `cmab-hub` 原 main 为 `643ea6431b3acb91dbf94251f3c989572f774807`，原样保留全部 57 条提交及 44 个受跟踪文件，历史分支为 `source/cmab-hub/main`；源仓库无额外分支或标签。补充整合提交以既有九项目 monorepo main 和 Hub 原 main 为父提交。已检查拟导入历史，未检出需清理的实际凭据；未改写 Hub 原始提交。

源工作区干净，没有待纳入的未提交代码或非代码材料。`frontend/dist`、`node_modules`、本地缓存和环境文件均未复制。原项目目录、origin、原始历史和在用构建产物保持不变；现有 nginx 继续使用原路径，本次不构建、不切换服务、不部署或归档。

MDM 既有整合不重做，两份设备 Excel 继续完全排除。此前九项目的文件树与所有既有历史引用保持不变。仓库侧栏简介不在本次修改范围。
