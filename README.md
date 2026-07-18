# 绡纹：蕾丝图案精选与识别网站

面向设计人员的纯 Python + Flask 工作台，包含本月 Top 10 图案、统一更新时间、上传匹配进度、临时文件名匹配、设计工单创建、客户信息登记和成衣预览占位页。

## 本地运行

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

也可以不激活环境，直接运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

浏览器访问 `http://127.0.0.1:5000`。

## GitHub Actions 构建 Docker 镜像

项目包含 `.github/workflows/docker-publish.yml`。代码推送到 GitHub 的 `main` 分支，或推送 `v*` 版本标签后，GitHub Actions 会构建 Linux AMD64 镜像并上传到 Docker Hub。

在 GitHub 仓库的 `Settings > Secrets and variables > Actions` 中配置：

- `DOCKERHUB_USERNAME`：Docker Hub 用户名。
- `DOCKERHUB_TOKEN`：在 Docker Hub `Account settings > Personal access tokens` 创建的访问令牌，不要填写账户密码。

默认镜像地址：

```text
DOCKERHUB_USERNAME/lace-pattern-workbench:latest
```

服务器运行示例：

```bash
docker pull DOCKERHUB_USERNAME/lace-pattern-workbench:latest
docker run -d --name lace-pattern -p 5000:5000 \
  -v lace-data:/app/data \
  -v lace-uploads:/app/uploads \
  --restart unless-stopped \
  DOCKERHUB_USERNAME/lace-pattern-workbench:latest
```

## 当前临时逻辑

- 匹配规则：上传文件名与 `pattern` 中的文件名相同即匹配成功。
- 匹配进度：前端通过约 2 至 3 秒的延时模拟。
- 成衣预览：目前是占位页面。
- 设计工单：登记客户姓名与联系方式后，按行保存到 `data/design_work_orders.jsonl`。

## 测试匹配

上传一个文件名为 `1.png` 至 `10.png` 的图片会返回匹配成功；其他文件名会返回“暂未找到您想要的款式”。
