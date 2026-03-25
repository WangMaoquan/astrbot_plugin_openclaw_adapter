# astrbot_plugin_openclaw_adapter

> OpenClaw 适配器 - 让 AstrBot 连接 OpenClaw 实现智能对话

## 功能

- 🤖 通过 HTTP API 调用 OpenClaw 获取智能回复
- 🔀 支持 responses 和 chat_completions 两种端点切换
- 💬 私聊自动回复，群聊 @触发
- 🛡️ 频率限制防止刷屏
- 🎯 空 @ 自动回复
- 📝 根据环境自动切换日志级别

## 配置

配置通过 AstrBot WebUI 进行，分为两组：

### 连接配置 (connection)

| 参数           | 说明                       | 默认值      |
| -------------- | -------------------------- | ----------- |
| PROTOCOL       | 协议类型 (http/https)      | `http`      |
| IP             | OpenClaw 服务器地址        | `localhost` |
| PORT           | OpenClaw HTTP API 端口     | `18789`     |
| OPENCLAW_TOKEN | 认证 Token（**必须配置**） | -           |

### 行为配置 (behavior)

| 参数                | 说明                     | 默认值                        |
| ------------------- | ------------------------ | ----------------------------- |
| AGENT_ID            | Agent ID                 | `main`                        |
| ADAPTER_TYPE        | 端点类型                 | `responses`                   |
| REPLY_EMPTY_MENTION | 群聊空 @时是否回复       | `true`                        |
| EMPTY_MENTION_REPLY | 空 @回复内容             | `我在~有什么可以帮你的吗？🍯` |
| RATE_LIMIT_SECONDS  | 频率限制（秒），0=不限制 | `10`                          |
| ALLOWED_USERS       | 允许触发的用户ID白名单   | -                             |

## 回复规则

| 场景         | 行为                          |
| ------------ | ----------------------------- |
| 私聊消息     | ✅ 所有消息都回复             |
| 群聊 @机器人 | ✅ 回复                       |
| 群聊无 @     | ❌ 不回复                     |
| 群聊空 @     | ✅ 回复默认内容（可配置关闭） |
| 频率限制内   | ❌ 不回复                     |
| 不在白名单   | ❌ 不回复                     |

## 用户白名单

配置 `ALLOWED_USERS` 可以限制谁可以触发 AI 回复：

- **留空**：所有人都可以触发
- **配置用户ID**：只有指定用户可以触发

获取用户ID方式：
1. 在 AstrBot 日志中查看消息记录
2. 或者在群里发送消息，查看日志中的 `user_id`

配置示例（多个用户用逗号分隔）：
```
12345678,87654321
```

## 端点切换

在 `behavior.ADAPTER_TYPE` 配置：

- `responses`: 使用 `/v1/responses` 端点（推荐）
- `chat_completions`: 使用 `/v1/chat/completions` 端点

修改后重启插件即可生效。

## 日志级别

- **开发环境**（IP 为 localhost/127.0.0.1）：DEBUG 级别，打印详细日志
- **生产环境**：INFO 级别，精简日志

## 安装

### 方式一：从 Git URL 安装

在 AstrBot WebUI → 插件市场 → 从 Git URL 安装：

```
https://github.com/WangMaoquan/astrbot_plugin_openclaw_adapter
```

### 方式二：本地安装

```bash
# 克隆到 AstrBot 插件目录
git clone https://github.com/WangMaoquan/astrbot_plugin_openclaw_adapter.git <你的astrbot安装目录下的plugin目录下>

# 配置 Token 后重载插件
```

## 获取 OpenClaw Token

1. 进入 OpenClaw Gateway 配置文件 `~/.openclaw/openclaw.json`
2. 找到 `gateway.auth.tokens` 数组
3. 复制其中一个 token 值

## 版本历史

- v1.0.0-beta.4 - 添加 HTTPS 支持，禁用 SSL 验证适配自签名证书
- v1.0.0-beta.3 - 添加用户白名单功能，增强安全性
- v1.0.0-beta.2 - 添加空 @回复、频率限制、环境日志切换
- v1.0.0-beta.1 - 基础功能：HTTP API 调用、群聊 @触发

## License

MIT
