# 上传到 GitHub

## 生成上传目录

打包脚本只复制明确允许的源码、网页、公开词库、模板、文档与工作流，并生成文件校验清单。真实 `.env`、DeepSeek 配置、缓存、日志与个人期刊指标不会进入上传目录。

```bash
python scripts/package_release.py
```

输出 `release/paper-search-web/` 和 `release/paper-search-web.zip`。输出已存在时，指定新的目录名重新生成：

```bash
python scripts/package_release.py --destination release/paper-search-web-next
```

脚本会检查常见密钥格式与示例中的密钥字段；上传前也应查看目录内容。后续新增的根目录文件需加入脚本的允许清单。

## 方式一：网页上传

1. 登录 GitHub，创建仓库，建议命名为 `paper-search-web`，按需求选择公开或私有。
2. 新仓库点击 `uploading an existing file`；已有仓库选择 **Add file → Upload files**。
3. 打开 `release/paper-search-web/`，把**内部文件与子目录**上传到仓库根目录。不要多套一层项目文件夹。
4. 确认 `.github/workflows/checks.yml`、`.gitignore`、`.env.example` 等点开头文件也已上传；系统隐藏文件可能需要开启显示。
5. 填写提交说明，例如 `Prepare paper search web project`，完成提交。

如使用 ZIP，请先解压，再上传文件夹内部内容。GitHub 网页文件上传不会自动把 ZIP 解压成源码。

## 方式二：使用 Git

在干净上传目录中执行：

```bash
git init -b main
git add .
git status --short
git commit -m "Prepare paper search web project"
```

从你的 GitHub 仓库页面复制实际远程地址，再执行：

```bash
git remote add origin <从你的仓库页面复制的Git地址>
git push -u origin main
```

`<...>` 是需要替换的说明，不能直接照抄。项目没有写入 GitHub 账号、访问令牌或远程地址。

## 上传后

- README 提供 Windows、macOS 和 Linux 的安装、配置与启动步骤。
- GitHub Actions 在推送和拉取请求后运行离线检查，无需 API Key，不调用真实论文或 AI 服务。远程执行结果以仓库 Actions 页面为准。
- 本项目需要 Python 后端。GitHub 存放源码；GitHub Pages 无法直接运行后端。默认服务地址是 `http://127.0.0.1:8000`。
- 当前未添加开源许可证。如准备授权他人使用、修改和分发，可由项目所有者选择许可证并添加 `LICENSE`。
