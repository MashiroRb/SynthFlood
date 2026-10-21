"""Standalone scientific figures; never overwrite paper's historical figure."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
RUNS=['results_m1','results_m1_s2','results_m1_s2b']


def plot():
    fig,axes=plt.subplots(1,3,figsize=(10,3),sharey=True)
    for ax,folder,label in zip(axes,RUNS,['Seed 1','Seed 2','Seed 2b']):
        rows=list(csv.DictReader((ROOT/folder/'m1_exams.csv').open()))
        for arm,color,marker in [('M0','#0072B2','o'),('B0','#666666','s'),('M2','#D55E00','^')]:
            cps=sorted({int(r['checkpoint']) for r in rows if r['phase']=='parity' and r['arm']==arm})
            rates=[]
            for cp in cps:
                cell=[int(r['chose_clone']) for r in rows if r['phase']=='parity' and r['arm']==arm and int(r['checkpoint'])==cp]
                rates.append(sum(cell)/len(cell))
            ax.plot(cps,rates,color=color,marker=marker,label=arm,linestyle='-' if arm=='M0' else '--')
        ax.set(title=label,xlabel='Clean episodes',ylim=(.35,1),xticks=[0,10,20])
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Parity clone choice')
    axes[-1].legend(frameon=False)
    fig.suptitle('Historical traces: M2 never reads memory yet answers change',fontsize=11)
    fig.tight_layout()
    for ext in ['png','pdf']:
        fig.savefig(ROOT/f'audit_m1/historical_with_M2.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    source=ROOT/'results_m1_v2/trajectory_cells.csv'
    if source.exists():
        rows=list(csv.DictReader(source.open()))
        seeds=sorted({r['seed'] for r in rows},key=int)
        fig,axes=plt.subplots(2,4,figsize=(12,6),sharex=True,sharey=True)
        for ax,seed in zip(axes.flat,seeds):
            for arm,color,marker in [('M0','#0072B2','o'),('B0','#666666','s'),('M2','#D55E00','^')]:
                selected=sorted([r for r in rows if r['seed']==seed and r['phase']=='parity' and r['arm']==arm],key=lambda r:int(r['checkpoint']))
                ax.plot([int(r['checkpoint']) for r in selected],[float(r['rate']) for r in selected],label=arm,color=color,marker=marker)
            ax.set(title=f'Seed {seed}',ylim=(0,1),xticks=[0,4,10,20]);ax.grid(alpha=.2)
        axes[0,0].legend(frameon=False)
        fig.supxlabel('Clean episodes after matched 20-episode warmup')
        fig.supylabel('Parity clone choice')
        fig.tight_layout()
        for ext in ['png','pdf']:
            fig.savefig(ROOT/f'results_m1_v2/parity_trajectories.{ext}',dpi=180,bbox_inches='tight')


if __name__=='__main__':
    plot()
