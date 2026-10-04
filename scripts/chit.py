#!/usr/bin/env python3
"""Chit: red/green proof bound to a git base. The model does not grade the test.

redgreen copies the changed tests onto a worktree at HEAD, runs the command,
and requires failure. Then it copies the full change and requires success.
verify rebuilds that worktree and re-runs both. A typed hash is not evidence.

Usage:
  python3 chit.py redgreen --repo . --label filter -- pytest orders/filter_test.py -q
  python3 chit.py verify --repo . .chit/filter.json

Exit 0 only on verdict BITES (redgreen) or CONFIRMED (verify).
Exit 1 on a real refusal or a failed re-run.
Exit 2 on usage or environment errors.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_PATH = __import__("re").compile(r"(test|spec|__tests__|fixture)", __import__("re").IGNORECASE)
TRIVIAL = {"true", "false", "echo", "printf", "yes", ":", "exit"}


def run(cmd: list[str], cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def git(repo: Path, args: list[str]) -> str:
    proc = run(["git", *args], repo)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def changed_files(repo: Path) -> list[str]:
    out = git(repo, ["status", "--porcelain", "-uall"])
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if path.startswith(".chit/") or path == ".chit":
            continue
        files.append(path)
    return files


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def refuse_trivial(cmd: list[str]) -> str | None:
    if not cmd:
        return "empty command"
    head = Path(cmd[0]).name
    if head in TRIVIAL:
        return f"trivial command: {head}"
    if head in {"python", "python3"} and len(cmd) >= 3 and cmd[1] == "-c" and "sys.exit(0)" in cmd[2] and "pytest" not in cmd[2]:
        return "python -c exit 0 is not a test"
    return None


def copy_files(repo: Path, dest: Path, files: list[str]) -> None:
    for rel in files:
        src = repo / rel
        target = dest / rel
        if not src.exists():
            if target.exists():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def execute(dest: Path, cmd: list[str], timeout: int) -> dict:
    try:
        proc = run(cmd, dest, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit": None, "timed_out": True, "sha256": None, "tail": ["timeout"]}
    except OSError as exc:
        return {"exit": None, "timed_out": False, "sha256": None, "tail": [f"ENV_FAIL: {exc.strerror or exc}"]}
    combined = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    lines = combined.splitlines()
    return {
        "exit": proc.returncode,
        "timed_out": False,
        "sha256": digest(combined),
        "tail": lines[-15:],
    }


def cause_of(red: dict) -> str:
    return " | ".join(red.get("tail") or [])[-240:]


def command_files(cmd: list[str], files: list[str]) -> list[str]:
    return [arg for arg in cmd if arg in files]


def redgreen(repo: Path, label: str, cmd: list[str], timeout: int) -> tuple[dict, int]:
    why = refuse_trivial(cmd)
    if why:
        return {"verdict": "REFUSED", "reason": why}, 1
    try:
        base = git(repo, ["rev-parse", "HEAD"]).strip()
    except RuntimeError as exc:
        return {"verdict": "REFUSED", "reason": str(exc)}, 2
    files = changed_files(repo)
    if not files:
        return {"verdict": "REFUSED", "reason": "no diff against HEAD"}, 1
    tests = [f for f in files if TEST_PATH.search(f)]
    code = [f for f in files if f not in tests]
    if not code:
        return {"verdict": "REFUSED", "reason": "diff has tests only; nothing to fix"}, 1
    ran = command_files(cmd, files)
    same = [path for path in ran if path in code]
    if same:
        return {"verdict": "REFUSED", "reason": f"test and fix in the same file: {same[0]}"}, 1

    parent = Path(tempfile.mkdtemp(prefix="chit-"))
    work = parent / "wt"
    try:
        add = run(["git", "worktree", "add", "--detach", str(work), base], repo)
        if add.returncode != 0:
            return {"verdict": "REFUSED", "reason": add.stderr.strip()}, 2
        copy_files(repo, work, tests)
        red = execute(work, cmd, timeout)
        copy_files(repo, work, code)
        green = execute(work, cmd, timeout)
    finally:
        run(["git", "worktree", "remove", "--force", str(work)], repo)
        shutil.rmtree(parent, ignore_errors=True)

    file_hashes = []
    for rel in files:
        p = repo / rel
        file_hashes.append({"path": rel, "sha256": sha256_file(p) if p.exists() else None, "role": "test" if rel in tests else "code"})

    if red.get("exit") is None or green.get("exit") is None:
        verdict = "ENV_FAIL"
    elif red.get("exit") in (0,):
        verdict = "DOES_NOT_BITE"
    elif green.get("exit") != 0 and red.get("sha256") == green.get("sha256"):
        verdict = "ENV_FAIL"
    elif green.get("exit") != 0:
        verdict = "STILL_RED"
    else:
        verdict = "BITES"
    cause = cause_of(red)
    ask_path = repo / ".chit" / "ask.json"
    oracle = ""
    if ask_path.exists():
        oracle = json.loads(ask_path.read_text(encoding="utf-8")).get("oracle") or ""
    if verdict == "BITES" and oracle and oracle not in cause:
        verdict = "WRONG_BITE"
    record = {
        "tool": "chit",
        "label": label,
        "verdict": verdict,
        "base": base,
        "command": cmd,
        "oracle": oracle,
        "cause": cause,
        "files": file_hashes,
        "red": red,
        "green": green,
    }
    out_dir = repo / ".chit"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{label}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["receipt"] = str(path)
    return record, 0 if verdict == "BITES" else 1


def verify(repo: Path, receipt_path: Path, timeout: int) -> tuple[dict, int]:
    record = json.loads(receipt_path.read_text(encoding="utf-8"))
    base = record.get("base")
    cmd = record.get("command")
    files = record.get("files") or []
    if not base or not cmd or not files:
        return {"verdict": "REJECTED", "reason": "receipt missing base, command, or files"}, 1
    tests = [f["path"] for f in files if f.get("role") == "test"]
    code = [f["path"] for f in files if f.get("role") == "code"]
    for item in files:
        p = repo / item["path"]
        if item.get("sha256") and p.exists() and sha256_file(p) != item["sha256"]:
            return {"verdict": "STALE", "reason": f"file changed since receipt: {item['path']}"}, 1
    parent = Path(tempfile.mkdtemp(prefix="chit-verify-"))
    work = parent / "wt"
    try:
        add = run(["git", "worktree", "add", "--detach", str(work), base], repo)
        if add.returncode != 0:
            return {"verdict": "REJECTED", "reason": add.stderr.strip()}, 2
        copy_files(repo, work, tests)
        red = execute(work, cmd, timeout)
        copy_files(repo, work, code)
        green = execute(work, cmd, timeout)
    finally:
        run(["git", "worktree", "remove", "--force", str(work)], repo)
        shutil.rmtree(parent, ignore_errors=True)
    bites = red.get("exit") not in (0, None) and green.get("exit") == 0
    cause = cause_of(red)
    ask_path = repo / ".chit" / "ask.json"
    oracle = ""
    if ask_path.exists():
        oracle = json.loads(ask_path.read_text(encoding="utf-8")).get("oracle") or ""
    oracle_ok = (not oracle) or (oracle in cause)
    confirmed = bites and oracle_ok
    out = {
        "verdict": "CONFIRMED" if confirmed else "REJECTED",
        "red_exit": red.get("exit"),
        "green_exit": green.get("exit"),
        "base": base,
        "cause": cause,
        "oracle_ok": oracle_ok,
    }
    return out, 0 if confirmed else 1


def start(repo: Path, label: str, locked: str, tier: str, nongol: str, test: str, rollback: str, oracle: str) -> tuple[dict, int]:
    if tier not in {"T0", "T1", "T2", "T3"}:
        return {"verdict": "REFUSED", "reason": "tier must be T0, T1, T2, or T3"}, 2
    if tier in {"T1", "T2"} and not test:
        return {"verdict": "REFUSED", "reason": "T1/T2 need --test, the exact command"}, 2
    if tier in {"T1", "T2"} and not oracle:
        return {"verdict": "REFUSED", "reason": "T1/T2 need --oracle, the taste the failing test must print"}, 2
    if tier == "T2" and not rollback:
        return {"verdict": "REFUSED", "reason": "T2 need --rollback before any edit"}, 2
    out_dir = repo / ".chit"
    out_dir.mkdir(exist_ok=True)
    record = {
        "label": label,
        "locked": locked,
        "tier": tier,
        "nongoal": nongol,
        "test": test,
        "rollback": rollback,
        "oracle": oracle,
    }
    path = out_dir / "ask.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["ask"] = str(path)
    record["next"] = "edit the repo, then run: python3 scripts/chit.py next --repo . --label " + label
    return record, 0 if tier != "T3" else 1


def next_step(repo: Path, label: str) -> tuple[dict, int]:
    ask_path = repo / ".chit" / "ask.json"
    script = "python3 scripts/chit.py"
    if not ask_path.exists():
        return {
            "do": f"{script} start --repo . --label {label} --tier T1 --locked \"...\" --nongoal \"...\" --test \"pytest path -q\"",
            "why": "sem contrato",
        }, 1
    ask = json.loads(ask_path.read_text(encoding="utf-8"))
    if ask.get("tier") == "T3":
        return {"do": "stop", "why": "T3: separe expand, backfill, switch. nao feche esta sessao"}, 1
    receipt = repo / ".chit" / f"{label}.json"
    report = repo / ".chit" / "report.html"
    if ask.get("tier") in {"T1", "T2"} and not receipt.exists():
        return {
            "do": f"{script} redgreen --repo . --label {label} -- {ask.get('test')}",
            "why": "falta a mordida no worktree",
        }, 1
    if receipt.exists():
        proof = json.loads(receipt.read_text(encoding="utf-8"))
        if proof.get("verdict") != "BITES":
            return {
                "do": f"{script} redgreen --repo . --label {label} -- {ask.get('test')}",
                "why": f"veredito {proof.get('verdict')}: o teste nao discriminou base e patch",
            }, 1
    if not report.exists():
        return {"do": f"{script} close --repo . --label {label}", "why": "falta o relatorio"}, 1
    text = report.read_text(encoding="utf-8")
    if "ENTREGUE" in text and "NAO_ENTREGUE" not in text:
        verified, _ = verify(repo, receipt, timeout=180)
        if verified.get("verdict") == "CONFIRMED" and verified.get("oracle_ok"):
            return {"do": "handoff", "why": "entregue", "report": str(report)}, 0
        return {
            "do": f"{script} redgreen --repo . --label {label} -- {ask.get('test')}",
            "why": "recibo ou pagina nao bate com a mordida reexecutada",
        }, 1
    return {"do": f"{script} close --repo . --label {label}", "why": "relatorio nao entregue, rode close de novo depois do conserto"}, 1


def esc(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def close(repo: Path, label: str, timeout: int) -> tuple[dict, int]:
    ask_path = repo / ".chit" / "ask.json"
    receipt_path = repo / ".chit" / f"{label}.json"
    if not ask_path.exists():
        return {"verdict": "REFUSED", "reason": "missing .chit/ask.json; run start first"}, 1
    ask = json.loads(ask_path.read_text(encoding="utf-8"))
    tier = ask.get("tier", "")
    verified: dict = {"verdict": "n/a"}
    proof: dict = {}
    if tier in {"T1", "T2"}:
        if not receipt_path.exists():
            return {"verdict": "REFUSED", "reason": f"missing {receipt_path.name}; run redgreen first"}, 1
        proof = json.loads(receipt_path.read_text(encoding="utf-8"))
        verified, _ = verify(repo, receipt_path, timeout)
    elif tier == "T3":
        return {"verdict": "REFUSED", "reason": "T3 does not close; split the change"}, 1
    smell_script = Path(__file__).with_name("diff_smell.py")
    smell = run([sys.executable, str(smell_script), "--repo", str(repo)], repo)
    smell_text = ((smell.stdout or "") + (smell.stderr or "")).strip() or "smells: none"
    smell_fail = "block\t" in smell_text or smell_text.startswith("block")
    gates = {
        "escopo": "PASS" if ask.get("locked") and ask.get("nongoal") else "FAIL",
        "risco": "FAIL" if tier == "T2" and not ask.get("rollback") else "PASS",
        "mordida": "PASS" if tier == "T0" or (verified.get("verdict") == "CONFIRMED" and verified.get("oracle_ok")) else "FAIL",
        "replay": "PASS" if tier == "T0" or verified.get("verdict") == "CONFIRMED" else "FAIL",
        "higiene": "FAIL" if smell_fail else "PASS",
    }
    delivered = all(v == "PASS" for v in gates.values())
    status = "ENTREGUE" if delivered else "NAO_ENTREGUE"
    report = {
        "status": status,
        "ask": ask,
        "panel": gates,
        "proof_verdict": proof.get("verdict"),
        "verify": verified,
        "command": proof.get("command"),
        "base": proof.get("base"),
        "red_exit": verified.get("red_exit"),
        "green_exit": verified.get("green_exit"),
        "files": [f.get("path") for f in proof.get("files") or []],
        "smells": smell_text,
        "rollback": ask.get("rollback") or "n/a",
        "cause": verified.get("cause") or "",
    }
    html = render_html(report)
    md = render_md(report)
    html_path = repo / ".chit" / "report.html"
    md_path = repo / ".chit" / "REPORT.md"
    html_path.write_text(html, encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    report["report"] = str(html_path)
    report["markdown"] = str(md_path)
    return report, 0 if delivered else 1


def render_md(report: dict) -> str:
    ask = report["ask"]
    cmd = " ".join(report.get("command") or []) or "n/a"
    files = ", ".join(report.get("files") or []) or "n/a"
    verify = (report.get("verify") or {}).get("verdict")
    return (
        f"# chit {report['status']}\n\n"
        f"pedido: {ask.get('locked')}\n\n"
        f"fora: {ask.get('nongoal')}\n\n"
        f"tier: {ask.get('tier')}\n\n"
        f"rollback: {report.get('rollback')}\n\n"
        f"painel: {report.get('panel')}\n\n"
        f"comando: `{cmd}`\n\n"
        f"base: {report.get('base') or 'n/a'}\n\n"
        f"vermelho: {report.get('red_exit')}  verde: {report.get('green_exit')}  verify: {verify}\n\n"
        f"causa do vermelho: {report.get('cause') or 'n/a'}\n\n"
        f"arquivos: {files}\n\n"
        f"smells:\n{report.get('smells')}\n\n"
        "Isto foi escrito pelo script. Frase do agente não substitui esta página.\n"
    )


def render_html(report: dict) -> str:
    ask = report["ask"]
    ok = report["status"] == "ENTREGUE"
    color = "#1f6b3a" if ok else "#8a2b2b"
    files = "".join(f"<li>{esc(p)}</li>" for p in (report.get("files") or [])) or "<li>n/a</li>"
    cmd = " ".join(report.get("command") or []) or "n/a"
    verify = (report.get("verify") or {}).get("verdict")
    css = (
        "body { font: 16px/1.45 ui-sans-serif, sans-serif; margin: 40px auto; max-width: 680px; color: #1c1c1c; }"
        "h1 { font-size: 28px; margin-bottom: 8px; color: " + color + "; }"
        "dt { margin-top: 14px; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: #666; }"
        "dd { margin: 2px 0 0; }"
        "pre { background: #f4f4f1; padding: 12px; overflow: auto; }"
    )
    return (
        "<!DOCTYPE html><html lang=\"pt\"><head><meta charset=\"utf-8\">"
        f"<title>chit {esc(report['status'])}</title><style>{css}</style></head><body>"
        f"<h1>{esc(report['status'])}</h1>"
        "<p>Prova reexecutada no worktree. Nao e um resumo do agente.</p><dl>"
        f"<dt>pedido</dt><dd>{esc(ask.get('locked'))}</dd>"
        f"<dt>fora desta entrega</dt><dd>{esc(ask.get('nongoal'))}</dd>"
        f"<dt>tier</dt><dd>{esc(ask.get('tier'))}</dd>"
        f"<dt>painel</dt><dd><code>{esc(report.get('panel'))}</code></dd>"
        f"<dt>comando</dt><dd><code>{esc(cmd)}</code></dd>"
        f"<dt>base</dt><dd><code>{esc(report.get('base') or 'n/a')}</code></dd>"
        f"<dt>vermelho / verde / verify</dt><dd>{esc(report.get('red_exit'))} / {esc(report.get('green_exit'))} / {esc(verify)}</dd>"
        f"<dt>causa do vermelho</dt><dd><code>{esc(report.get('cause') or 'n/a')}</code></dd>"
        f"<dt>arquivos</dt><dd><ul>{files}</ul></dd>"
        f"<dt>smells</dt><dd><pre>{esc(report.get('smells'))}</pre></dd>"
        "</dl></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Unfakeable red/green proof")
    sub = parser.add_subparsers(dest="op", required=True)
    rg = sub.add_parser("redgreen")
    rg.add_argument("--repo", default=".")
    rg.add_argument("--label", default="chit")
    rg.add_argument("--timeout", type=int, default=180)
    rg.add_argument("cmd", nargs=argparse.REMAINDER)
    vf = sub.add_parser("verify")
    vf.add_argument("--repo", default=".")
    vf.add_argument("--timeout", type=int, default=180)
    vf.add_argument("receipt")
    st = sub.add_parser("start")
    st.add_argument("--repo", default=".")
    st.add_argument("--label", default="chit")
    st.add_argument("--tier", required=True)
    st.add_argument("--locked", required=True)
    st.add_argument("--nongoal", default="nada alem do pedido")
    st.add_argument("--test", default="")
    st.add_argument("--oracle", default="")
    st.add_argument("--rollback", default="")
    cl = sub.add_parser("close")
    cl.add_argument("--repo", default=".")
    cl.add_argument("--label", default="chit")
    cl.add_argument("--timeout", type=int, default=180)
    nx = sub.add_parser("next")
    nx.add_argument("--repo", default=".")
    nx.add_argument("--label", default="chit")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if args.op == "redgreen":
        cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
        if not cmd:
            parser.error("pass the test command after --")
        record, code = redgreen(repo, args.label, cmd, args.timeout)
    elif args.op == "verify":
        record, code = verify(repo, Path(args.receipt), args.timeout)
    elif args.op == "start":
        record, code = start(repo, args.label, args.locked, args.tier, args.nongoal, args.test, args.rollback, args.oracle)
    elif args.op == "next":
        record, code = next_step(repo, args.label)
    else:
        record, code = close(repo, args.label, args.timeout)
    print(json.dumps(record, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
