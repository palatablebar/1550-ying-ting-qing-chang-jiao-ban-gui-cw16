"""Minimal pytest-compatible runner for environments without pytest.

Supports the subset used by this repository: module-scoped ``pytest.fixture``,
function argument injection by name, ``pytest.raises`` and plain asserts.
Discovery mirrors pytest: test_*.py files with test_* functions/classes.
"""
import argparse
import importlib
import inspect
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace


class _Raises:
    def __init__(self, expected, match=None):
        self.expected = expected
        self.match = match
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f'{self.expected.__name__} not raised')
        if not issubclass(exc_type, self.expected):
            return False
        if self.match is not None and self.match not in str(exc):
            raise AssertionError(f'pattern {self.match!r} not found in {exc!s}')
        self.value = exc
        return True


class _PytestShim:
    @staticmethod
    def raises(expected, match=None):
        return _Raises(expected, match)

    @staticmethod
    def fixture(*args, **kwargs):
        def wrap(func):
            func._pytest_fixture = True
            func._scope = kwargs.get('scope', 'function')
            return func
        if args and callable(args[0]):
            return wrap(args[0])
        return wrap

    @staticmethod
    def parametrize(argnames, argvalues):
        names = [n.strip() for n in argnames.split(',')]

        def wrap(func):
            func._params = [(dict(zip(names, case)) if isinstance(case, tuple)
                             else {names[0]: case}) for case in argvalues]
            return func
        return wrap

    class mark:
        @staticmethod
        def parametrize(argnames, argvalues):
            return _PytestShim.parametrize(argnames, argvalues)


sys.modules.setdefault('pytest', _PytestShim)


class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value):
        old = getattr(target, name)
        self._undo.append((target, name, old))
        setattr(target, name, value)

    def undo(self):
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)
        self._undo.clear()


class _Registry:
    def __init__(self):
        self.funcs = {}
        self.module_cache = {}
        self.scope_cache = {}
        self.monkeypatch = _MonkeyPatch()

    def fixture(self, func, scope):
        self.funcs[func.__name__] = (func, scope)

    def resolve(self, name, target_globals):
        if name == 'monkeypatch':
            return self.monkeypatch
        if name in self.funcs:
            func, scope = self.funcs[name]
            if scope in ('module', 'session'):
                key = (func.__module__, name)
                if key not in self.scope_cache:
                    self.scope_cache[key] = self.invoke(func)
                return self.scope_cache[key]
            return self.invoke(func)
        if name in target_globals:
            value = target_globals[name]
            if getattr(value, '_pytest_fixture', False):
                return self.resolve(name, value.__globals__)
            return value
        raise KeyError(name)

    def invoke(self, func):
        kwargs = {}
        for name in inspect.signature(func).parameters:
            kwargs[name] = self.resolve(name, func.__globals__)
        return func(**kwargs)


def collect_module(path, registry):
    sys.path.insert(0, str(Path(__file__).parent))
    module = importlib.import_module(path.stem)
    for name, obj in vars(module).items():
        if callable(obj) and getattr(obj, '_pytest_fixture', False):
            registry.fixture(obj, getattr(obj, '_scope', 'function'))
    return module


def run_file(path, registry):
    module = collect_module(path, registry)
    failures = 0
    passed = 0
    for name, obj in sorted(vars(module).items()):
        if not name.startswith('test_') or not callable(obj):
            continue
        params = getattr(obj, '_params', None)
        cases = params if params else [None]
        for index, param in enumerate(cases):
            label = f'{path.stem}::{name}' + (f'[{index}]' if params else '')
            try:
                kwargs = {}
                for arg in inspect.signature(obj).parameters:
                    if param and arg in param:
                        kwargs[arg] = param[arg]
                    else:
                        kwargs[arg] = registry.resolve(arg, obj.__globals__)
                obj(**kwargs)
                passed += 1
                print(f'PASS {label}')
            except Exception:  # noqa: BLE001
                failures += 1
                print(f'FAIL {label}')
                traceback.print_exc()
            finally:
                registry.monkeypatch.undo()
    return passed, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='*', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / '..' / 'src'))
    paths = args.paths or sorted(root.glob('test_*.py'))
    registry = _Registry()
    # Load conftest fixtures first, mirroring pytest's root conftest discovery.
    conftest = root / 'conftest.py'
    if conftest.exists():
        collect_module(conftest, registry)
    total_passed = total_failed = 0
    for path in paths:
        passed, failed = run_file(path, registry)
        total_passed += passed
        total_failed += failed
    print(f'\n{total_passed} passed, {total_failed} failed')
    return 1 if total_failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
