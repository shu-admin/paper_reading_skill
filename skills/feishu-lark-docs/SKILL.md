---
name: feishu-lark-docs
description: 使用 lark-cli（飞书官方开源 CLI）读取飞书/Lark 云文档并完成其他飞书工作。当用户提供飞书链接或 token（feishu.cn、larksuite.com、doubao.com 的 /docx/、/wiki/ 路径），要求读取、总结、搜索文档内容，处理文档内嵌的表格、图片、画板，或需要安装配置 lark-cli（npm install、config init、auth login）时使用。
---

# 飞书文档（lark-cli）

复用 `lark-cli`：token 刷新、分页、DocxXML/Markdown 转换全部由 CLI 封装，无需自实现开放平台 API 调用。

## 快速路径

```sh
lark-cli docs +fetch --doc <url-or-token>
```

`--doc` 接受完整 URL 或 token，支持 `/docx/`、`/wiki/`（自动解析到 docx）、带 `#share-...` 的选区链接。旧教程中的 `--api-version v2` 已是默认行为，可省略（传入也不报错）。

**身份策略：不加 `--as`，用默认 auto**（user 优先，缺失自动回退 bot）。应用已被文档协作者共享时 bot 即可读取，无需用户授权。仅在报权限不足（permission denied / forbidden）或要访问仅个人可见的文档时，才显式 `--as user` 并走「环境引导」第 3 步授权。

环境未就绪（命令报 config 错误）时先走「环境引导」，否则直接按下面的策略读取。

## 读取策略：最小范围优先

**只有确需整篇时才省略 `--scope`。** 按已知信息选模式：

| 已知信息 | 写法 | 后续动作 |
|---------|------|---------|
| 具体术语/错误码 | `--scope keyword --keyword '部署\|发布'` | 上下文不足时，用返回的 `top-block-id` 转 `section`/`range` |
| 章节或标题 | `--scope outline --max-depth 3` | 取标题 ID 后 `--scope section --start-block-id <id>` |
| 精确起止位置 | `--scope range --start-block-id <id> --end-block-id <id>` | `-1` 表示读到末尾 |
| 不了解结构 | `--scope outline` | 依目录转入 `section` 或 `range` |
| 确需整篇 | 省略 `--scope` | - |

`--keyword` 依次尝试子串、归一化、分词形变、RE2 正则；`|` 表示 OR，任一命中即返回。`--context-before`/`--context-after` 可补命中块前后的顶层兄弟块。

### 输出解读

- 响应 JSON 的 `data.document.content` 是正文；`reference_map` 是 sidecar（资源属性、评论），与正文属同一份响应，**保留完整 JSON，不要拆散**。评论不保证全返回，完整评论用 `drive +list-comments`。
- 设 `--scope` 后 `content` 外层是 `<fragment>`；子节点出现 `<excerpt top-block-id="...">` 表示只返回了容器/表格的节选，**不要假设已拿到整个顶层块**，需要时用 `top-block-id` 重新读取。
- 表格默认瘦身（只返回表头 + 命中行）；读整表用 `--scope range --start-block-id <table-id> --end-block-id <table-id>`。
- `--detail`：`simple`（默认，浏览/总结）、`with-ids`（定位/跳转，block ID 可用于后续编辑和直达链接）、`full`（含样式元数据，编辑前用）。
- `--doc-format markdown` 得纯文本；默认 `xml` 保留结构与评论锚点。

### 文档内嵌资源路由

| 返回内容 | 处理 |
|---------|------|
| `<img>` / `<source>` | 有公开可信 `url` 时可下载；无则提取 token，预览用 `docs +media-preview`，下载用 `docs +media-download` |
| `<whiteboard>` | 提取 token，用 `docs +media-download` |
| `<sheet>` / `<cite file-type="sheets">` | 提取 token 和 sheet-id，转 `lark-cli skills read lark-sheets` |
| `<bitable>` / `<cite file-type="bitable">` | 提取 token 和 table-id，转 `lark-cli skills read lark-base` |
| `<synced_reference>` | 提取 `src-token` 和 `src-block-id`，读源文档并定位 block |

下载安全规则：仅请求公开可信的 HTTPS URL，拒绝 userinfo、内网/环回/链路本地等地址，逐次校验重定向。

## 环境引导（环境未就绪时才执行）

第 1 步无需用户配合；第 2、3 步用户需在浏览器完成授权。

### 1. 安装

```sh
npm install -g @larksuite/cli
```

### 2. 配置飞书自建应用

```sh
lark-cli config init --new
```

阻塞式：后台运行，从输出提取验证 URL 发给用户，确认后再继续。非交互场景用 `--app-id <id> --app-secret-stdin`；已有应用的 Agent 环境改用 `lark-cli config bind`，避免重复建应用。

### 3. 授权用户身份

```sh
lark-cli auth login
```

Device Flow，同样阻塞。分回合环境：先 `lark-cli auth login --no-wait --json` 取验证 URL，发给用户并结束回合；用户确认后 `lark-cli auth login --device-code <code>` 收尾。

完成后 `lark-cli auth status` 应显示 user 身份 ready。bot 身份无需登录（租户权限）。日常健康检查 `lark-cli doctor`；升级 `lark-cli update`。

第 3 步分回合发起时，响应 hint 会要求生成二维码：`lark-cli auth qrcode --output ./qr.png <verification_url>`。注意 `--output` 只接受当前目录内的相对路径（绝对路径会被安全校验拒绝）。

## 其他飞书工作

- 先查域：`lark-cli <domain> --help`（im、calendar、sheets、base、task、mail、drive、wiki 等）
- 同类任务优先 `+shortcut` 高层命令，如 `lark-cli calendar +agenda`
- 调 API 前查参数与 scopes：`lark-cli schema <service.resource.method>`
- 兜底：`lark-cli api GET /open-apis/...` 按路径直调任意端点
- 深入某域读内置 skill：`lark-cli skills list`；文档创建/编辑/导入/素材/历史版本读 `lark-cli skills read lark-doc`；认证与 scope 排查读 `lark-cli skills read lark-shared`

## 安全约定

每个命令的 `--help` 标注风险级别：read / write / high-risk-write。high-risk-write 必须先取得用户明确确认，再补 `--yes` 执行；写操作可先 `--dry-run` 预览。

## 更多细节

引导流程参数、身份选择、`+fetch` 完整 flags、常见错误排查见 [reference.md](reference.md)。