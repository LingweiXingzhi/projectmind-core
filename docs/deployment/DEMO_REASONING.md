# 演示用低思考强度

DeepSeek V4（包括 `deepseek-v4.1-flash`）与官方滚动别名 `deepseek-flash` / `deepseek-pro` 默认请求低思考强度。模型名、API 密钥、端点、超时、JSON 校验与人工确认规则保持原有设置。

Chat Completions 发送 `thinking.type=enabled` 和 `reasoning_effort=low`；Responses 发送 `reasoning.effort=low`。这是真实模型请求参数，不是只修改页面文字，也不是改变 ZCode 或 Codex 自身的思考强度。

服务端可设置 `PROJECTMIND_AI_REASONING_EFFORT=low|high|max|none`；`none` 在 Chat Completions 只发送关闭思考字段，不同时传思考强度。其他模型和旧版 DeepSeek 不附加这些字段。非法配置在启动模型工作者前拒绝，错误不回显配置值。

公共状态及架构工作台显示“请求思考强度：低”。兼容服务商仍须支持并执行这些参数；请求携带 low 不等于已证明服务商内部调度方式，也不保证所有复杂项目能在固定时间完成。JSON 约束失败不会当成成功候选，生成结果仍需用户确认。

官方参数说明：[DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)（2026-10-08 核对）。
