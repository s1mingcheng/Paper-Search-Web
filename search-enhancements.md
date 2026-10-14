# 论文检索增强方案

核对日期：2026-10-13。以下区分本次已实现与后续建议，接口配额以服务方当前账号政策为准。

## 本次已实现

- 浅色墨绿工作台、可折叠 AI 配置、检索指南、桌面和移动端布局。
- 综合研究、计算机 / 数理、生物医学、跨库广搜四组数据源预设；实时显示已选数据源数。
- 近 5 个自然年快捷设置、年份输入校验、标题 / 标题与摘要匹配范围、排除词。
- 有摘要 / 开放获取 / 有 DOI 的当前结果筛选。
- 结果展示 DOI、关键词命中词和命中字段；按标题命中优先于摘要命中的启发式相关度排序。
- 修复严格匹配为空时返回全部候选记录的问题；期刊名称与发表类型不再作为主题命中依据。
- OpenAlex 支持 `OPENALEX_API_KEY`，仅在服务端通过 Authorization 请求头发送，不回传前端。

相关度分数只表示当前关键词覆盖与命中位置，不表示论文质量、真实性或 AI 置信度。没有摘要的论文仍可凭标题命中；严格模式可能降低召回率，建议结合「任一包含」交叉检索。筛选后的数量是本次请求范围内的结果，不是全库总量。

## 建议功能与外部接口

| 优先级 | 功能 | 上游接口 | 收益与接入要点 |
| --- | --- | --- | --- |
| P0 | 多页检索、断点续查与失败来源重试 | 现有各数据库的分页接口 | 当前每库候选数最多 100，输出最多 50；容易遗漏较深分页。逐库使用 cursor / offset / token，保存实际抓取范围和停止原因，处理 429、超时与缓存。不能把每库输出上限称为全库检索。 |
| P0 | 人工确认双语扩展词 | 现有 translator / DeepSeek | 先预览每组同义词、缩写和翻译来源，允许删除泛化词，再发起检索。特别避免 AI、ML 等缩写带来的歧义。 |
| P1 | 前向引用、参考文献与相似论文 | `GET https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations`、`/references`；`POST https://api.semanticscholar.org/recommendations/v1/papers` | 从高质量种子论文扩展文献，减少术语差异导致的遗漏；保存种子和追踪关系，限制层数与总量，按 API 政策申请密钥。 |
| P1 | DOI 与发表状态核验 | `GET https://api.crossref.org/works/{doi}` | 补齐作者、期刊、发表信息及更正 / 撤稿关联；显示来源和核验时间。缺少状态字段只能标记「未查到相关更新」，不能判定「未撤稿」。 |
| P1 | 开放版本查找 | `GET https://api.unpaywall.org/v2/{doi}?email=联系邮箱` | 根据 DOI 补充开放状态与合法全文链接，标明版本、许可和来源。它用于 DOI 查询；旧关键词搜索接口已于 2026-09-18 退役，不应作为新增全文搜索源。 |
| P2 | 机构仓储与开放文献覆盖 | CORE API v3，`https://api.core.ac.uk/v3/`，works 搜索资源 | 补充机构仓储等开放文献；申请 API Key，按账号权限和限额接入。元数据可用不等于全文可下载；上线前用获授权账号验证字段和查询契约。 |
| P2 | 检索历史、版本关系、增量更新 | 本地持久化记录 + 现有上游数据源 | 保存用户检索式、有效扩展词、源响应、分页范围及时间。合并 DOI 与无 DOI 的同题记录时，同时核对作者、年份，保留预印本与正式版本关系。 |
| P2 | 中文与订阅数据库 | 机构授权的知网 / 万方 / Web of Science / Scopus 等接口或馆藏服务 | 弥补中文与付费出版覆盖，具体接口依据机构合同获取。当前六个公开源的中英双语扩展不能等同于中文数据库覆盖。 |

## 建议新增的本地接口（未实现）

所有路由沿用当前服务，便于前端统一调用；无需为每个学术源开放一个本地端口。

| 路由 | 用途 |
| --- | --- |
| `POST /api/query/preview` | 返回候选扩展词，让用户确认后检索；带策略版本，避免用户确认后再次静默扩展。 |
| `POST /api/search/jobs` | 建立可分页任务，返回 job_id，支持去重、配额与页数上限。 |
| `GET /api/search/jobs/{id}` | 返回逐源进度、已抓取数量、失败原因和部分结果。 |
| `POST /api/search/jobs/{id}/cancel` | 服务端取消任务；目前「终止检索」只中止浏览器等待，已发出的上游请求可能继续。 |
| `GET /api/papers/{id}/related?relation=citations` | 查引用、参考文献或相似论文，保留结果来源。 |
| `GET /api/papers/resolve?doi=...` | 校验 DOI、发表状态、开放版本，返回字段级来源与查询时间。 |
| `GET /api/search/history` | 查看已保存检索策略和执行记录。 |

本地网页与这些 API 共用 `127.0.0.1:8000`。开发时如拆分前端，可用 `5173` 作为前端开发端口、`8000` 作为后端端口并配置代理；生产环境使用 HTTPS `443`，上游学术 API 也使用 HTTPS `443`。这里增强全面性的是数据源和检索策略，增加端口数量本身不会改善搜索。

## 验证与配置

离线测试：`python -m unittest discover -s tests -v`。测试覆盖严格模式空结果、AND / OR、缩写边界、字段范围、排除词、排序、跨源合并与 OpenAlex 请求头密钥。

可选环境变量：`OPENALEX_API_KEY`、`SEMANTIC_SCHOLAR_API_KEY`、`NCBI_API_KEY`、`OPENALEX_EMAIL`、`CROSSREF_MAILTO`、`NCBI_EMAIL`。环境变量修改后需要重启本地服务。不要把密钥写入前端脚本。

## 官方参考

- [OpenAlex 认证与配额](https://help.openalex.org/api/authentication/)：基础调用可不带 Key，申请免费 Key 可提高日预算；支持 Bearer 请求头。
- [Semantic Scholar Academic Graph](https://api.semanticscholar.org/api-docs/graph) 与 [Recommendations](https://api.semanticscholar.org/api-docs/recommendations)。
- [CORE API 介绍与密钥申请](https://core.ac.uk/services/api)：提供元数据与全文访问能力，需依账号授权接入。
- [Unpaywall REST API](https://data.unpaywall.org/products/api)：按 DOI 查询，需联系邮箱；旧关键词搜索接口已退役。
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)：元数据与发表更新，包含来自 Retraction Watch 等可信来源的数据。
