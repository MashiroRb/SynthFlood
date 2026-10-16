#!/bin/bash
# Auto-publish: waits for the M1-S2 and P4-N100 completion markers, computes
# compact summaries, then commits+pushes ALL new results to GitHub (same repo).
# Failure-honest: if a run dies without its marker, publishes what exists and
# marks the run aborted in the summary.
set -u
CODE=/root/synthflood/code
LOGD=/root/synthflood/logs
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOGD/autopublish.log; }

cd $CODE
git config user.email "lab@synthflood.local"
git config user.name "synthflood-lab"

m1s2_status() {
  # 0 = done marker; 1 = still running; 2 = died without marker
  [ -f $LOGD/m1s2.done ] && return 0
  if [ -s /tmp/m1s2_full.pid ] && ! kill -0 $(cat /tmp/m1s2_full.pid) 2>/dev/null; then
    sleep 240  # grace period: pipeline may still be finalizing
    kill -0 $(cat /tmp/m1s2_full.pid) 2>/dev/null && return 1
    echo "aborted: full-run pid died without done marker" >> $LOGD/m1s2.done
    return 0
  fi
  return 1
}
p4_status() {
  [ -f $LOGD/p4n100.done ] && return 0
  if [ -s /tmp/p4n100.pid ] && ! kill -0 $(cat /tmp/p4n100.pid) 2>/dev/null; then
    sleep 240
    kill -0 $(cat /tmp/p4n100.pid) 2>/dev/null && return 1
    echo "aborted: runner pid died without done marker" >> $LOGD/p4n100.done
    return 0
  fi
  return 1
}

say "watcher start: waiting for m1s2.done + p4n100.done"
for i in $(seq 1 720); do   # up to 24h
  m1s2_status; M=$?
  p4_status;  P=$?
  [ $M -eq 0 ] && [ $P -eq 0 ] && break
  sleep 60
done
say "markers resolved (m1s2=$M p4=$P); summarizing + publishing"

python3 - <<'PY'
import csv, json, math, os
def wilson(p, n, z=1.96):
    if n == 0: return None
    c = (p + z*z/(2*n)) / (1 + z*z/n)
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [round(c-h,4), round(c+h,4)]
def rate(path, pred):
    rows=[r for r in csv.DictReader(open(path)) if pred(r)]
    n=len(rows)
    k=sum(int(r["chose_clone"] if "chose_clone" in r else (int(r["chosen_is_synthetic"]))) for r in rows)
    return n, k/n if n else None
out={}
d="results_m1_s2"
if os.path.isdir(d) and os.path.exists(f"{d}/m1_exams.csv"):
    exams=list(csv.DictReader(open(f"{d}/m1_exams.csv")))
    sig={}
    for arm in ("PRE","B0","M0","M2","M3","M4"):
        for cp in ("0","2","4","6","8","10","12","14","16","18","20"):
            rs=[r for r in exams if r["arm"]==arm and r["phase"]=="exam" and r["checkpoint"]==cp]
            if rs:
                n=len(rs); k=sum(int(r["chose_clone"]) for r in rs)
                sig[f"{arm}@exam{cp}"]={"sigma":round(k/n,4),"n":n,"ci95":wilson(k/n,n)}
    for arm in ("B0","M0","M2","M3"):
        for cp in ("0","10","20"):
            rs=[r for r in exams if r["arm"]==arm and r["phase"]=="parity" and r["checkpoint"]==cp]
            if rs:
                n=len(rs); k=sum(int(r["chose_clone"]) for r in rs)
                sig[f"{arm}@parity{cp}"]={"sigma":round(k/n,4),"n":n,"ci95":wilson(k/n,n)}
    out["m1_s2"]={"sigma":sig,
                  "note":"seed-2028 replication; judgment rules in m1/PRE_REG_M1_S2.md"}
res={}
import glob
for f in sorted(glob.glob("results_csv/*_n100_sweep.csv")):
    stage=os.path.basename(f).replace("_sweep.csv","").upper()
    rows=list(csv.DictReader(open(f)))
    byeps={}
    for e in ("0.0","0.75"):
        rs=[r for r in rows if abs(float(r["eps"])-float(e))<1e-6]
        if not rs: continue
        n=len(rs)
        succ=sum(int(r["success_full"]) for r in rs)/n
        reg=sum(float(r["reward"]) for r in rs)/n
        byeps[e]={"n":n,"success":round(succ,4),"mean_reward":round(reg,4)}
    res[stage]=byeps
if res:
    json.dump(res, open("results_csv/N100_DEFENSE_SUMMARY.json","w"), indent=1)
if out:
    os.makedirs("results_m1_s2", exist_ok=True)
    json.dump(out, open("results_m1_s2/S2_SUMMARY.json","w"), indent=1, ensure_ascii=False)
print("summaries written")
PY

git add -A results_m1_s2 results_csv data/contamination_s2 m1 2>/dev/null || git add -A results_m1_s2 results_csv data/contamination_s2
git commit -q -m "M1 seed-2 replication + defense battery N=100: results, caches, summaries" || true
for i in 1 2 3; do
  if git push -q https://MashiroRb:$(cat /root/.pat)@github.com/MashiroRb/SynthFlood.git main 2>/dev/null; then break; fi
  sleep 10
done
REV=$(git rev-parse --short HEAD)
say "PUBLISHED rev=$REV"
