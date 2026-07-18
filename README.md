# 蕾智创库：蕾丝图案精选与识别网站

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

- 本月精选：图片存放在 `pattern/top10`。
- 素材库原图：存放在 `pattern/library/pic/originals`。
- 素材库缩略图：存放在 `pattern/library/pic/thumbnails`，文件名格式为 `1_thumb.jpg`。
- 素材数据：存放在 `pattern/library/data`，素材库页面会读取其中的季度 CSV。
- 匹配规则：上传文件名与 `pattern/library/pic/originals` 中的文件名相同即匹配成功。
- 提交约定：`pattern/library` 下的网站基础数据、原图和缩略图提交到 Git，并随 Docker 镜像发布。
- 匹配进度：前端通过约 2 至 3 秒的延时模拟。
- 成衣预览：目前是占位页面。
- 设计工单：登记客户姓名与联系方式后，按行保存到 `data/design_work_orders.jsonl`。

## 素材上传接口

接口地址为 `POST /api/library/materials`，使用环境变量 `MATERIAL_UPLOAD_TOKEN` 配置访问令牌，并通过请求头 `Authorization: Bearer <token>` 鉴权。

支持 `multipart/form-data`，字段如下：

- `styleId`：素材数字编号，必填。
- `code`：款式编号，例如 `LACE-081`。
- `category`：分类或花纹类型。
- `width`：幅宽，例如 `150cm`。
- `material`：材质或成分。
- `usage`：推荐用途。
- `color`：颜色。
- `description`：素材说明。
- `image`：素材原图，支持 PNG、JPG、WEBP、BMP。

上传示例：

```bash
curl -X POST "https://rbcc.302922.xyz/api/library/materials" \
  -H "Authorization: Bearer YOUR_MATERIAL_UPLOAD_TOKEN" \
  -F "styleId=81" \
  -F "code=LACE-081" \
  -F "category=植物花卉纹" \
  -F "width=150cm" \
  -F "material=锦纶混纺" \
  -F "usage=礼服" \
  -F "color=象牙白" \
  -F "description=适合轻礼服罩层" \
  -F "image=@81.png"
```

接口也接受不带图片的 JSON 请求，用于新增或更新素材元数据。上传记录保存在 `data/material_catalog.db`，图片保存在 `data/material_library`，两者由现有 Docker 数据卷持久化。

## 测试匹配

将测试图片放入 `pattern/library/pic/originals`，上传同名图片会返回匹配成功；其他文件名会返回“暂未找到您想要的款式”。
