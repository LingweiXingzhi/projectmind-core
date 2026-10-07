"""Stable machine errors; adapters must not branch on translated messages."""

ERRORS = {
    "INVALID_INPUT": "输入不符合工作区合同",
    "NOT_FOUND": "工作区、草稿或版本不存在",
    "REVISION_CONFLICT": "草稿或正式版本已改变，请重新读取",
    "STALE_CONTEXT": "图、仓库或代码版本不属于当前上下文",
    "EVIDENCE_MISMATCH": "证据引用与固定代码版本不一致",
    "HUMAN_REVIEW_REQUIRED": "需要绑定实际预览的人工审核",
    "REVIEW_EXPIRED": "审核预览已过期",
    "REVIEW_REPLAY": "不能以旧确认令牌执行另一项决定",
    "REQUEST_FORBIDDEN": "审核请求不来自有效本机会话",
    "PUBLIC_ADAPTER_REQUIRED": "此写操作需要 A 的受保护请求适配器",
    "REFERENCE_CONFLICT": "删除对象仍被引用",
    "DIRTY_ARCHITECTURE_REPO": "架构工作副本有未预期的修改",
    "PUBLICATION_FAILED": "架构 Git 发布尚未完成，可以检查后重试",
    "PUBLICATION_CONFLICT": "发布期间架构分支或文件发生变化",
    "VERSION_CONFLICT": "不可变版本内容不能覆盖",
    "STORAGE_FAILED": "工作区存储不可用",
}


class WorkspaceError(ValueError):
    def __init__(self, code, detail=None):
        self.code = code
        self.detail = detail or ERRORS[code]
        super().__init__(self.detail)

    def as_dict(self):
        return {"error": {"code": self.code, "message": self.detail}}


def require(condition, code="INVALID_INPUT", detail=None):
    if not condition:
        raise WorkspaceError(code, detail)
