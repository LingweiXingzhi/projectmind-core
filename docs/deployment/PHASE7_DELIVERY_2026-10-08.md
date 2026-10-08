# 第七阶段前置交付：坏协议响应控制

## Result / Files Changed

补齐 Responses.output/message/content 与 Chat.choices/message/content 类型检查，合法JSON但错误协议形状返回受控AIError。
仅改 archloop/ai_transport.py、对应边界测试与计划/记录。整体deadline/取消仍未实现，不混作本轮完成。

## Verification

固定 local48e2b1327c661191d708c83ae5e5051e023b5da5=remote43d5a611f22a45b1433cf746ad4fe21b10f5bd9d，同树82d18619100de0e5a743b19db8df2ac2a9b070ee。
传输边界6项/1.524秒、实际本机协议/登录后生成10项/4.975秒全部通过。多种合法JSON错误形状不再抛普通TypeError/AttributeError。
未重跑全量/GUI/TLS；前阶段1008全量与后续界面结果仅作基线。本机协议使用合成密钥和预写JSON，真实AI未运行。
后续提交仅此记录，不变运行源码。

## Project Model Impact

MINOR，已定义传输模块内部错误控制；正式Model未改。

## Risks / Follow-up

整体请求墙钟截止、可取消资源释放与重试治理继续按NEXT_RESUME_PLAN推进。
公网资源、原生浏览器、真实模型/任务验证器、完整上游Git历史与权威综述仍未满足。
依赖PR67，独立Draft，不合main。
