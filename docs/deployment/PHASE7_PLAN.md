# 第七阶段前置：协议响应形状

先检查最新已交付树PR67和模型适配差异。发现外层JSON对象通过解析后，Responses.output 或 Chat.choices/message 若类型错误，会触发普通TypeError/AttributeError，而不是受控AIError。
先补齐这个具体边界，再按NEXT_RESUME_PLAN处理整体deadline/取消；不把输入类型修复当作已完成墙钟截止。
只改传输读取与相关边界测试；合成返回覆盖两种协议，无真实模型调用。
固定提交后跑模型协议/边界与生成相关回归，再上传独立Draft，核验远端树与main；不修改正式Model。
Project Model Impact：MINOR，已定义传输职责内部的错误控制补齐。
