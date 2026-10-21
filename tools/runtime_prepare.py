"""Run with the original app's --run-script facility (CPython 3.10)."""
from pathlib import Path
import dis
import hashlib
import inspect
import json
import marshal
import sys
import traceback
import types

ROOT = Path(__file__).resolve().parents[1]


def flatten(code, parent=""):
    result = {}
    key = parent + "." + code.co_name if parent else code.co_name
    result[key] = code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            result.update(flatten(const, key))
    return result


def compile_sources():
    compiled = ROOT / "work" / "compiled"
    compiled.mkdir(parents=True, exist_ok=True)
    evidence = ROOT / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    main_source = ROOT / "source" / "main.py"
    main = compile(main_source.read_text(encoding="utf-8"), "main.py", "exec", dont_inherit=True, optimize=0)
    (compiled / "main.marshal").write_bytes(marshal.dumps(main))
    original = marshal.loads((ROOT / "bytecode" / "main.pyc").read_bytes()[16:])
    old = flatten(original); new = flatten(main)
    comparison = []
    for name, code in old.items():
        other = new.get(name)
        comparison.append({"code": name, "present": other is not None, "old_instructions": len(list(dis.get_instructions(code))), "new_instructions": len(list(dis.get_instructions(other))) if other else None, "argnames_match": other is not None and code.co_varnames[:code.co_argcount] == other.co_varnames[:other.co_argcount], "same_opcodes": other is not None and [i.opname for i in dis.get_instructions(code)] == [i.opname for i in dis.get_instructions(other)]})
    info = {"python": sys.version, "executable": sys.executable, "frozen": bool(getattr(sys,"frozen",False)), "main_source_sha256": hashlib.sha256(main_source.read_bytes()).hexdigest(), "main_comparisons": comparison}
    (ROOT / "evidence" / "runtime_compile.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def inspect_interfaces():
    from PyQt6 import QtCore
    from app.core import video_renderer
    from app.common.workers import RenderWorker, TranscribeWorker, VoiceWorker
    info = {"python": sys.version, "qt": QtCore.QT_VERSION_STR, "renderer_functions": {}, "workers": {}}
    for name, value in vars(video_renderer).items():
        if name.startswith("_") or not (inspect.isfunction(value) or inspect.isclass(value)):
            continue
        if getattr(value,"__module__","") != video_renderer.__name__:
            continue
        try: sig=str(inspect.signature(value))
        except Exception: sig="unknown"
        info["renderer_functions"][name]=sig
    for worker in (RenderWorker,TranscribeWorker,VoiceWorker):
        methods={}
        for name in ("__init__","run","cancel"):
            try: methods[name]=str(inspect.signature(getattr(worker,name)))
            except Exception: pass
        info["workers"][worker.__name__]=methods
    (ROOT / "evidence" / "runtime_interfaces.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


try:
    action=sys.argv[1] if len(sys.argv)>1 else "compile"
    result=compile_sources() if action=="compile" else inspect_interfaces()
    (ROOT / "evidence" / "runtime_status.txt").write_text("PASS " + action,encoding="utf-8")
except BaseException:
    (ROOT / "evidence" / "runtime_status.txt").write_text(traceback.format_exc(),encoding="utf-8")
    raise
