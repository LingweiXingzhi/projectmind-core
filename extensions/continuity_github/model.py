"""Legacy record contract with optional, independently validated references."""
from extensions.continuity.model import *
from extensions.continuity import model as original
from extensions.continuity_github.references import references, all_references


def validate_logs(values):
    clean = original.validate_logs(values)
    for raw, item in zip(values, clean):
        item['references'] = references(raw.get('references', []))
    return clean


def validate_packet(packet):
    clean = original.validate_packet(packet)
    raw = packet.get('record', {})
    clean['references'] = references(raw.get('references', []))
    clean['logs'] = validate_logs(raw.get('logs', []))
    return clean


def render_resume(record):
    out = original.render_resume(record)
    refs = all_references(record)
    if refs:
        out += '\n\n## 关联工作项与代码\n\n链接与说明由参与者填写；Issue/PR 状态未联网核实。代码核查须核对仓库与固定提交。\n'
        for r in refs:
            # Plain locators, no untrusted Markdown labels.
            out += '\n- ' + r['url'] + '\n  说明：' + r['reason'].replace('\n', ' ').replace('<', '&lt;')
    return out


def ai_context(record):
    return original.ai_context(record) + '\n\n' + render_resume(record).split('## 关联工作项与代码', 1)[-1] if all_references(record) else original.ai_context(record)
