# CMC Platform

本仓库汇集 8 个 CMC 项目的代码与 Git 历史。各项目放在同名子目录中，保持导入时的源文件内容；这次整合不代表已完成业务功能、启动方式或部署的运行时集成。

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

## 历史、分支与标签

原始提交不改写。整合主分支的初始提交以 8 个源 main 提交作为父提交，并将各项目的原始文件树放入对应子目录。原历史中的文件路径仍位于各自仓库根目录。

- 原分支保留为 `source/<项目名>/<原分支名>`，分支指向原始提交。
- 原标签保留为 `source/<项目名>/<原标签名>`，保留原标签对象。
- 来源仅为 GitHub 已提交的分支和标签，不包含本地未提交或未推送的内容。
- Issues、Pull Requests、Actions secrets、运行记录等非 Git 数据未复制。

## 后续开发

在本仓库工作副本的对应项目子目录中开发，通过本仓库 main 或新功能分支提交。个人原仓库保留，本次不设置向原仓库的自动同步。旧项目目录及其 origin 不变。

`cmc-cost-modeler` 和原 code/archive 中的项目不属于本仓库。
