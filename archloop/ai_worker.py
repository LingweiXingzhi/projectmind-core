"""One disposable model-call worker. IPC only; never keys in argv/files."""
import json
import sys

from .ai_transport import AIError, AITimeout, _CALL_DEADLINE, _call_chat_completions, _call_responses


def main():
    try:
        # Parent bounds this private pipe message before starting a worker.
        request = json.loads(sys.stdin.buffer.read(4 * 1024 * 1024 + 1))
        _CALL_DEADLINE.set(request['deadline'])
        function = _call_responses if request['config']['protocol'] == 'responses' else _call_chat_completions
        value = function(request['config'], request['instructions'], request['payload'],
                         request['schemaName'], request['schema'], request['timeout'])
        response = {'ok': True, 'value': value}
    except AIError as exc:
        response = {'ok': False, 'message': str(exc)[:2048],
                    'kind': 'timeout' if isinstance(exc, AITimeout) else 'error'}
    except Exception:
        response = {'ok': False, 'message': '模型工作者未完成有效响应。'}
    sys.stdout.buffer.write(json.dumps(response, ensure_ascii=False, allow_nan=False).encode())
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
