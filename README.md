# OpenClaw 适配器

> 连接 OpenClaw Gateway 实现智能对话

## 功能

- 通过 HTTP API 调用 OpenClaw 获取智能回复
- 支持 responses 和 chat_completions 两种端点切换
- 完整的 QQ 消息收发

## 配置

配置通过 `_conf_schema.json` 定义，默认值如下：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| IP | OpenClaw 服务器地址 | localhost |
| PORT | OpenClaw HTTP API 端口 | 18789 |
| ADAPTER_TYPE | 端点类型 (responses/chat_completions) | responses |
| OPENCLAW_TOKEN | 认证 Token | (你的token) |
| AGENT_ID | Agent ID | main |
| TIMEOUT | 请求超时(秒) | 30 |

## 端点切换

在 astrbot 配置页面修改 `ADAPTER_TYPE`：
- `responses`: 使用 `/v1/responses` 端点
- `chat_completions`: 使用 `/v1/chat/completions` 端点

修改后重启插件即可生效。

## API 地址

- responses: `http://<IP>:<PORT>/v1/responses`
- chat_completions: `http://<IP>:<PORT>/v1/chat/completions`