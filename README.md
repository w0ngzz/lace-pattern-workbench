# 蕾智创库：蕾丝图案精选与识别网站

面向设计人员的纯 Python + Flask 工作台，包含本月 Top 10 图案、统一更新时间、远程 Worker 图案匹配、实时匹配进度、设计工单创建、客户信息登记和成衣预览占位页。

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

服务器使用 Compose 运行 Web 与 WebSocket Gateway：

```bash
cp deploy.env.example .env
# 编辑 .env，设置 MATCHER_TOKEN 和 MATCH_FILE_SECRET。
docker compose --env-file .env -f docker-compose.prod.yml pull
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

`web` 与 `gateway` 必须挂载同一个 `lace-pattern-runtime` 卷。Cloudflare Tunnel 分别将网站域名指向 `web:5000`，将 Worker 域名指向 `gateway:8765`。

## 图案匹配流程

1. 浏览器上传参考图，后端保存图片并创建 `requestId`。
2. 后端生成 10 分钟有效的签名下载链接，将 `match_request` 写入共享运行目录。
3. Gateway 通过 WebSocket 把任务发送给已认证的远程 Worker。
4. Worker 下载图片、执行识别，并通过同一个 WebSocket 返回 `match_result`。
5. Gateway 将结果写入共享运行目录，浏览器轮询结果接口并展示素材序号与相似度。
6. Worker 在 120 秒内未返回时，页面提示超时，并允许用户创建设计工单。

Worker 成功回包示例：

```json
{
  "type": "match_result",
  "requestId": "32位小写十六进制任务编号",
  "workerId": "lace-worker-01",
  "ok": true,
  "matched": true,
  "matches": [
    {"imageIndex": 23, "similarity": 0.9231}
  ],
  "elapsedMs": 1260,
  "modelVersion": "lace-v1"
}
```

`imageIndex` 对应 `pattern/library/pic/originals` 下素材文件名的数字部分，例如 `23.png`。`similarity` 使用 `0` 到 `1` 的小数；后端也兼容 `materialId` 和 `score` 字段名。

## 当前逻辑

- 本月精选：图片存放在 `pattern/top10`。
- 素材库原图：存放在 `pattern/library/pic/originals`。
- 素材库缩略图：存放在 `pattern/library/pic/thumbnails`，文件名格式为 `1_thumb.jpg`。
- 素材数据：存放在 `pattern/library/data`，素材库页面会读取其中的季度 CSV。
- 匹配规则：以远程 Worker 返回的素材序号和相似度为准，不再使用上传文件名匹配。
- Worker 下载：后端为上传图案生成 10 分钟有效的签名下载链接，并随匹配任务发送。
- 提交约定：`pattern/library` 下的网站基础数据、原图和缩略图提交到 Git，并随 Docker 镜像发布。
- 匹配进度：前端每秒轮询真实任务状态，等待时显示渐进进度，完成后显示 Worker 结果。
- 成衣预览：目前是占位页面。
- 设计工单：登记客户姓名与联系方式后，按行保存到 `data/design_work_orders.jsonl`。

## 自动化测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖任务创建、签名图片下载、Worker 成功匹配、未命中、处理失败、超时和设计工单流程。
