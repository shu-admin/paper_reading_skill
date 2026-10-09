# lark-cli 参考细节

## 安装与升级

```sh
npm install -g @larksuite/cli   # 安装（Node 18+）
lark-cli update                 # 升级到最新版
lark-cli doctor                 # 健康检查：版本/配置/授权/连通性
```

版本兼容：`--api-version v2` 在 1.0.92 仍被接受；v2 已是默认行为，新版本若报 unknown flag 直接去掉该参数。官方文档示例已不再使用该参数。

## 配置应用（config）

```sh
lark-cli config init --new      # 引导创建新的自建应用（推荐）
lark-cli config init --app-id <id> --app-secret-stdin   # 非交互：App Secret 从 stdin 读入
lark-cli config init --brand feishu                      # 指定品牌：feishu | lark
lark-cli profile                # 多应用配置管理（--name 可命名 profile）
```

交互式 `config init` 阻塞：后台运行，从输出提取验证 URL 发给用户。已有应用的 Agent 环境（OPENCLAW_HOME / HERMES_HOME 等）会默认拒绝 init，改用 `lark-cli config bind` 绑定现有应用；确需独立应用才加 `--force-init`。

## 用户授权（auth）

```sh
lark-cli auth login                              # Device Flow，阻塞直到用户完成
lark-cli auth login --no-wait --json             # 仅发起，返回设备码与验证 URL（agent 分回合场景）
lark-cli auth login --device-code <code>         # 用户确认授权后完成登录
lark-cli auth login --domain docs,calendar       # 按域申请 scopes
lark-cli auth login --recommend                  # 仅申请推荐（自动批准）scopes
lark-cli auth qrcode                             # 二维码（ASCII / PNG）
lark-cli auth status                             # 查看身份与 token 状态
```

openId 与用户名在 `auth status` 输出中。授权域列表：application approval apps attendance base calendar contact docs drive event im mail markdown mindnotes minutes note okr sheets slides task vc wiki whiteboard all。

## 身份选择

| 身份 | 适用 | 说明 |
|------|------|------|
| 不加 `--as`（默认 auto） | 首选 | 优先 user，缺失时自动回退 bot；应用可见的文档零配置可读 |
| `--as bot` | 应用/租户身份 | 无需登录；只能访问应用有权限的资源 |
| `--as user` | 仅个人可见的文档、需要用户身份的操作 | 需完成 auth login；遇到 permission denied 时显式指定并授权 |

## docs +fetch 完整 flags

`--doc`（URL 或 token；支持 `/docx/`、`/wiki/`、`#share-...` 选区链接）、`--scope`（full\|outline\|section\|range\|keyword）、`--keyword`（子串/归一化/分词形变/RE2 正则，`\|` OR）、`--start-block-id`/`--end-block-id`（range/section 锚点；end 传 `-1` 表示到文档末尾）、`--context-before`/`--context-after`（选中块前后的顶层兄弟块；命中在容器/表格内时被忽略）、`--max-depth`（outline 标题层级上限；其他 scope 控制子树深度，`0` 仅块自身、`-1` 不限）、`--doc-format`（xml\|markdown\|im-markdown，默认 xml）、`--detail`（simple\|with-ids\|full，默认 simple）、`--revision-id`（`-1` 最新）、`--lang`（zh-CN 等）、`--jq`、`--dry-run`、`--as`。

## 常见错误

| 现象 | 处理 |
|------|------|
| user identity missing | `lark-cli auth login` 后重试 |
| unsupported --doc input | 仅支持 docx URL/token 或可解析到 docx 的 wiki 链接；旧版 .doc 等格式换 `lark-cli drive` 导出 |
| scope 不足 | 读 `lark-cli skills read lark-shared` 按指引补 scope 或重登 |
| 命令不存在 | `lark-cli <domain> --help` 查当前版本命令；或 `lark-cli api` 兜底 |
| 请求被拒 | 确认 `--as` 身份与文档权限匹配（个人文档用 user） |

## 内置 skills（lark-cli 自带）

`lark-cli skills list` 查看全部。读取方式：

```sh
lark-cli skills read lark-doc                                # 文档全工作流：创建/编辑/导入/素材/历史版本
lark-cli skills read lark-doc/references/lark-doc-fetch.md   # +fetch 深入参考（官方）
lark-cli skills read lark-shared                             # 认证与 scope 排查
lark-cli skills read lark-sheets                             # 表格
lark-cli skills read lark-base                               # 多维表格
```

以 `lark-cli skills read` 读取，保证内容与当前 CLI 版本同步。