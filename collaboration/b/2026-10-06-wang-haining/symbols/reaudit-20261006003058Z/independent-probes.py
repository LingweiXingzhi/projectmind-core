import sys
from repo_index.symbols import parse_symbols
print('Python:', sys.version.split()[0])

def assert_case(label, path, source, expected, warnings=[]):
    actual = parse_symbols(path, source)
    assert actual == {
        'path': path, 'language': 'python', 'status': 'ok',
        'symbols': expected, 'warnings': warnings,
    }, (label, actual)
    print(label + ': PASS')

def symbol(name, qualified, kind, start, end, doc=None):
    return {'name': name, 'qualified_name': qualified, 'kind': kind,
            'start_line': start, 'end_line': end, 'docstring': doc}

source = '''class Outer:
    while ready:
        with lock:
            def action(self):
                if ready:
                    def child(): pass
                else:
                    class Product:
                        async def run(self): pass
    else:
        def tail(self): pass

def outside(): pass
'''
assert_case('while/with/else scope restored', 'pkg/control.PYI', source, [
    symbol('Outer', 'Outer', 'class', 1, 11),
    symbol('action', 'Outer.action', 'method', 4, 9),
    symbol('child', 'Outer.action.child', 'function', 6, 6),
    symbol('Product', 'Outer.action.Product', 'class', 8, 9),
    symbol('run', 'Outer.action.Product.run', 'async_method', 9, 9),
    symbol('tail', 'Outer.tail', 'method', 11, 11),
    symbol('outside', 'outside', 'function', 13, 13),
])

source = '''class Case:
    match name:
        case "x":
            def found(self): pass
        case _:
            async def fallback(self): pass
'''
assert_case('match/case nearest class', 'pkg/case.py', source, [
    symbol('Case', 'Case', 'class', 1, 6),
    symbol('found', 'Case.found', 'method', 4, 4),
    symbol('fallback', 'Case.fallback', 'async_method', 6, 6),
])

assert_case('empty docstring remains empty', 'pkg/doc.py', 'def empty():\n    ""\n    pass\n', [
    symbol('empty', 'empty', 'function', 1, 3, ''),
])
cleaned = 'x' * 2000
assert_case('docstring limit after cleanup', 'pkg/doc.py', 'def exact():\n    """\n        ' + cleaned + '\n    """\n    pass\n', [
    symbol('exact', 'exact', 'function', 1, 5, cleaned),
])

for label, source, line in [
    ('indentation error line', 'class Example:\n    def ok(self): pass\n  def bad(): pass\n', 3),
    ('mixed newline NUL location', 'def ok():\r\n    pass\r\n# comment\r\x00', 4),
    ('surrogate source guarded', 'def bad():\n    "\ud800"\n', None),
]:
    actual = parse_symbols('pkg/error.py', source)
    assert set(actual) == {'path','language','status','symbols','warnings'}, actual
    assert actual['status'] == 'parse_error' and actual['symbols'] == [] and actual['warnings'], actual
    if line is not None:
        assert f'line {line}:' in actual['warnings'][0], actual
    assert all(isinstance(warning, str) for warning in actual['warnings']), actual
    print(label + ': PASS; ' + actual['warnings'][0])
