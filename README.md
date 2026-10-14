# 智研 · Paper Search Web

在本机运行的论文检索与整理工作台。支持中英双语关键词、多数据库查询、关键词命中校验、摘要阅读与 Excel 导出，可选接入 DeepSeek 辅助选词与生成中文摘要概括。

**环境要求：Python 3.10+，现代浏览器。** 后端使用 Python 标准库 HTTP 服务，前端为原生 HTML / CSS / JavaScript，无需 Node.js 或前端构建工具。

## 功能

- 同时检索 OpenAlex、Crossref、arXiv、Semantic Scholar、PubMed 与 Europe PMC。
- 本地中英词库和可选在线翻译，支持「全部包含」与「任一包含」概念组合。
- 综合研究、计算机 / 数理、生物医学、跨库广搜四种数据源组合。
- 年份范围、标题 / 标题与摘要匹配、排除词及关键词命中依据。
- DOI 或标题去重、来源过滤、关键词相关度 / 年份 / 引用数排序。
- 按有摘要、开放获取或有 DOI 筛选当前结果。
- 可选 DeepSeek 扩展词与中文摘要概括。
- 导出包含论文、来源状态和检索说明的 Excel 文件。

## 快速启动

下载或克隆仓库，进入含有 `app.py` 的项目目录。

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py --open
```

如已安装的 Python 使用 `python` 命令，将第一行的 `py -3` 换为 `python`。完成依赖安装后，也可运行 `powershell -ExecutionPolicy Bypass -File .\start.ps1`；脚本优先使用项目的 `.venv`。

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --open
```

访问 **http://127.0.0.1:8000**。`--open` 自动打开浏览器，不需要时可省略。修改端口示例：

```bash
python app.py --port 8001
```

上述简写 `python` 需要指向已安装依赖的解释器；未激活虚拟环境时请沿用完整 `.venv` 路径。

默认只监听本机地址。上传到 GitHub 后仍需运行 Python 后端；GitHub Pages 无法直接运行此项目后端。

## 可选配置

复制 `.env.example` 为项目根目录的 `.env`，按需填写，再启动服务。`.env` 自动加载；系统环境变量中的同名设置优先。示例文件的密钥字段请保持为空。

```powershell
# Windows
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

| 变量 | 用途 |
| --- | --- |
| `PAPER_SEARCH_HOST` / `PAPER_SEARCH_PORT` | 监听地址与端口，默认 `127.0.0.1:8000` |
| `DEEPSEEK_API_KEY` | AI 选词与摘要概括 |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 默认 `https://api.deepseek.com` / `deepseek-chat` |
| `DEEPSEEK_MAX_ITEMS` | 每次摘要概括上限，默认 20，范围 1–50 |
| `OPENALEX_API_KEY` | OpenAlex 认证，仅服务端通过请求头发送 |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar 认证 |
| `NCBI_API_KEY` | PubMed / NCBI 认证 |
| `OPENALEX_EMAIL` / `CROSSREF_MAILTO` / `NCBI_EMAIL` | 各数据源联系邮箱 |
| `TRANSLATION_PROVIDER` | `auto`：本地词库 + MyMemory；`local` / `none`：只使用本地词库 |
| `MYMEMORY_EMAIL` | 可选 MyMemory 联系邮箱 |

也可在页面保存 DeepSeek Key，保存在本机 `data/deepseek_config.json`；启动时环境变量中的 Key 优先。启用 AI 时，检索词或摘要会发送给 DeepSeek。配置、缓存与 `.env` 均不进入 Git 或发布包。

如需个人期刊指标，复制 `data/journal_metrics.example.csv` 为 `data/journal_metrics.csv` 后填写有权使用的数据。正式数据文件已被忽略，不进入发布包；当前界面不显示商业 JCR 影响因子。

## 使用步骤与边界

1. 输入研究概念，例如 `人工智能, 医学`，用逗号、分号或换行分隔。
2. 选择关键词关系、年份、每库上限，按需设置匹配范围和排除词。
3. 选择数据源组合后开始检索，查看各源的成功状态、失败原因与耗时。
4. 核对扩展词及标题 / 摘要命中依据，按需筛选、排序和阅读摘要。
5. 如已配置 DeepSeek，可概括摘要，最后导出 Excel。

排除词在标题与摘要中按字面匹配，不自动扩展同义词。严格匹配为空时不会回退到未匹配候选；可主动改为「任一包含」扩大范围。

每库上限与候选数有上限，尚未实现全库分页续查。术语差异、摘要缺失和源服务限流可能影响召回；相关度反映关键词覆盖与命中位置，不代表论文质量。「终止检索」结束浏览器等待，已发出的上游请求可能继续。

## 项目结构

```text
paper-search-web/
├── app.py                      # HTTP 服务、数据源适配与导出
├── deepseek.py                 # AI 选词与摘要
├── translator.py               # 中英双语扩展
├── requirements.txt            # Python 依赖
├── start.ps1                   # Windows 启动脚本
├── .env.example                # 空白配置模板
├── .gitignore                  # 本机文件排除规则
├── .gitattributes              # 跨系统换行规则
├── static/                     # 网页、样式与图标
├── data/
│   ├── zh_en_terms.csv          # 公开中英词库
│   └── journal_metrics.example.csv
├── docs/                       # 上传指南、增强方案、演示说明
├── scripts/package_release.py  # 生成干净上传目录与 ZIP
├── tests/                      # 离线检索与打包检查
└── .github/workflows/checks.yml # GitHub 自动检查
```

程序在运行时创建的私有配置和缓存保存在 `data/` 下，已被 Git 忽略。

## HTTP API

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/health` | 服务状态 |
| `GET /api/sources` | 数据源列表 |
| `POST /api/search` | 论文检索 |
| `GET /api/deepseek/status` | AI 配置状态，不返回完整密钥 |
| `POST /api/deepseek/config` | 保存或清除本机 AI 配置 |
| `POST /api/summarize` | AI 摘要概括 |
| `POST /api/export` | 生成 Excel |

检索请求示例：

```json
{
  "keywords": "machine learning, education",
  "sources": ["openalex", "crossref"],
  "match_mode": "all",
  "match_scope": "title_abstract",
  "exclude_keywords": "protocol",
  "from_year": 2020,
  "max_results": 10,
  "use_deepseek_terms": false
}
```

## 检查与上传

使用已安装依赖的 Python：

```bash
python -m unittest discover -s tests -v
python scripts/package_release.py
```

脚本生成 `release/paper-search-web/` 和 `release/paper-search-web.zip`，仅包含允许发布的文件。上传目录内部的内容即可；网页上传时先解压 ZIP。

详细步骤见 [GitHub 上传指南](docs/github-upload.md)。GitHub Actions 已配置 Linux / Windows 离线检查，远程执行结果以仓库 Actions 页面为准。

## 更多说明

- [功能与接口增强方案](docs/search-enhancements.md)
- [演示录制说明](docs/demo-recording-script.md)
- 数据来自公开 API，使用前请核对正式发表版本及数据源条款。
- 双语扩展不等于接入知网、万方等中文数据库；订阅数据源需获得合法接口授权。
- 项目尚未指定开源许可证。如计划授权他人使用、修改和分发，请由项目所有者选择并添加 `LICENSE`。
