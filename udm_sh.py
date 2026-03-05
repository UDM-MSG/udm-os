#!/usr/bin/env python
# udm_sh.py - tiny interactive shell on top of udmctl
import subprocess, shlex, sys

BANNER = """
UDM-sh (type 'help' or 'exit')
Examples:
  status
  simulate ai --mode safe --iters 25
  test-ai --scenarios 240 --seed 42 --blockspec "SAFE:3,RISKY:1"
  thresholds --s_open 0.70
  config-get
"""

def run_cmd(line):
    if not line.strip(): return
    if line.strip() in ("exit","quit"): raise SystemExit
    if line.strip() in ("help","?"):
        print(BANNER); return
    cmd = f"python ./udmctl.py {line}"
    try:
        out = subprocess.check_output(shlex.split(cmd), stderr=subprocess.STDOUT)
        print(out.decode("utf-8", errors="ignore"))
    except subprocess.CalledProcessError as e:
        print(e.output.decode("utf-8", errors="ignore"))

def main():
    print(BANNER)
    while True:
        try:
            line = input("udm> ")
            run_cmd(line)
        except (KeyboardInterrupt, EOFError):
            print("\nbye"); break

if __name__ == "__main__":
    main()
