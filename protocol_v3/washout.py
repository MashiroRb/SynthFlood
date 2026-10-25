import argparse
import copy

from .common import *
from .executor import CheckedClient, tokenizer
from .worker import Evaluator
from paired_sweep_ratingfix.common import COMMON_PROMPT


def full_memory(mem):
    if not mem.entries:
        return ''
    return ('Your experience notes from earlier shopping sessions:\n' +
            '\n'.join(f"- [{e['type']}] {e['text']}" for e in mem.entries))


def run(shard):
    validate()
    from m1.m1_memory import MemoryStore, induce_lesson
    from synthflood.select_env import SelectEnv, product_fields
    from synthflood.vllm_client import LLMClient
    directory = OUT/f'washout{shard}'
    if (directory/'STARTED.json').exists():
        raise RuntimeError('Refusing uncontrolled washout resume')
    write(directory/'STARTED.json',dict(shard=shard))
    tok = tokenizer()
    backend = digest(read(directory/'hardware.json'))
    ev = Evaluator(directory, tok, backend)
    shopping = read(DATA/'washout.json')
    exams = read(DATA/'exams.json')
    for seed in SEEDS[shard::2]:
        for group in ('M0','B0'):
            mem = MemoryStore(str(directory/f'seed{seed}'/f'memory_{group}.json'),group)
            if mem.entries:
                raise RuntimeError('Memory must start empty under the new protocol')
            def shop(plan, t, phase):
                case = dict(phase='shopping',condition=f'{group}:{phase}',task_id=plan['task_id'],
                    seed=seed,rotation=plan['rotation'],k=6 if phase=='pollution' else 0,
                    family='mix',block=dict(goal=plan['goal']),candidates=plan['candidates'],arm=group)
                # Prevent identical task/seed keys between different episodes.
                case['episode'] = t
                result = ev.evaluate(case,copy.deepcopy(plan['candidates']),COMMON_PROMPT,full_memory(mem))
                chosen = next((c for c in plan['candidates'] if c['cid']==result['chosen_cid']),None)
                description = None if chosen is None else f"'{product_fields(chosen['item'])['title']}' at ${chosen['price_float']:.2f}"
                # Missing reward is preserved explicitly in the memory. It is
                # never converted into a purchase or a zero-valued observation.
                if result['valid']:
                    mem.add_observation(t,plan['goal']['query'],result['chosen_kind'],result['reward'],
                                        result['gold_reward'],choice_description=description)
                else:
                    mem.entries.append(dict(type='observation',t=t,arm=group,
                        text=f"Episode {t}: task '{plan['goal']['query']}'. No purchase completed; task failed ({result['exclusion_reason']}); official reward unavailable.",
                        data=dict(chosen_kind='none',reward=None,gold_reward=result['gold_reward'])))
                if t%5==0:
                    checked=CheckedClient(LLMClient(8000,MODEL),tok,directory/'requests'/f'lesson_{seed}_{group}_{t}.jsonl.gz')
                    lesson=induce_lesson(checked,mem,t,seed=seed*10000+t,temperature=0)
                    if lesson is None:
                        raise RuntimeError('Lesson generation failed; memory protocol would be incomplete')
                mem.save()
            def exam(checkpoint):
                memory=full_memory(mem)
                before=digest(mem.entries)
                write(directory/f'seed{seed}'/f'checkpoint_{group}_{checkpoint:02d}.json',
                    dict(entries=mem.entries,injected_context=memory,context_sha256=digest(memory)))
                for i,q in enumerate(exams):
                    case=dict(phase='exam',condition=f'{group}:cp{checkpoint}:{q["family"]}',
                        task_id=q['task_id'],seed=seed,rotation=q['order'],k=1,
                        family=q['family'],block=dict(goal=q['goal']),candidates=q['candidates'],
                        arm=group,group=group,checkpoint=checkpoint)
                    ev.evaluate(case,copy.deepcopy(q['candidates']),COMMON_PROMPT,memory)
                    if i%100==0:
                        print('EXAM_PROGRESS',shard,seed,group,checkpoint,i,flush=True)
                assert digest(mem.entries)==before,'Exam changed memory'
            if group=='M0':
                for t,p in enumerate(shopping[str(seed)]['pollution'],1):
                    shop(p,t,'pollution')
            exam(0)
            offset=40 if group=='M0' else 0
            for t,p in enumerate(shopping[str(seed)]['clean'],1):
                shop(p,offset+t,'clean')
                if t%2==0:
                    exam(t)
            assert sum(e['type']=='observation' for e in mem.entries)==(80 if group=='M0' else 40)
            assert sum(e['type']=='lesson' for e in mem.entries)==(16 if group=='M0' else 8)
        # Cache only within this seed's paired groups; preserve explicit reuse
        # provenance but avoid retaining all eight trajectories in host memory.
        ev.cache.clear()
    validate()
    write(directory/'COMPLETE.json',dict(validated=True,seeds=list(SEEDS[shard::2])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('shard',type=int)
    run(p.parse_args().shard)
