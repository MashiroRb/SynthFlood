"""Repair metadata in the previous frozen blocks without resampling anything."""
import collections
import copy
import json
import shutil
import tarfile

from .common import ROOT, DATA, OUT, ARMS, COUNTS, ROTATIONS, REVISION
from .common import read, write, file_sha, candidates, digest
from synthflood.product_metadata import restore_raw_metadata, rating_and_count
from synthflood.select_env import SelectEnv, product_fields, results_page
from synthflood.defenses import structural_score, _page_text

PARENT = ROOT/'data/paired_n98_v1'
PARENT_MANIFEST_SHA = '9afde444d8eaadb9f994e991aa0178ef6f2176338fd64f2bf4d31ad8694e5f67'
EDITABLE_ITEM_FIELDS = {'Rating','num_reviews','total_reviews'}


def prepare():
    if DATA.exists() or OUT.exists():
        raise RuntimeError('Versioned run already exists; refusing overwrite')
    assert not any(a.startswith('ppr') for a in ARMS) and len(ARMS)==15
    if file_sha(PARENT/'manifest.json')!=PARENT_MANIFEST_SHA:
        raise ValueError('Parent manifest changed')
    parent=read(PARENT/'manifest.json')
    archive=ROOT/'results_paired_n98_v1/worker0/code-snapshot.tar.gz'
    # Historical code remains recoverable from its immutable experiment archive.
    with tarfile.open(archive,'r:gz') as snapshot:
        for name,expected in parent['source_sha256'].items():
            path=ROOT/name
            if path.exists() and file_sha(path)==expected:
                continue
            import hashlib
            archived=snapshot.extractfile(name)
            if archived is None or hashlib.sha256(archived.read()).hexdigest()!=expected:
                raise ValueError('Parent source cannot be reconstructed: '+name)
    raw_by_asin={p['asin']:p for p in read(PARENT/'selected_raw.json')}
    DATA.mkdir(parents=True)
    shutil.copyfile(PARENT/'selected_raw.json',DATA/'selected_raw.json')
    coverage=collections.defaultdict(collections.Counter)
    changed_fields=collections.Counter();lane_sizes={};checks=0;reward_checks=0;page_checks=0
    preview=[]
    for lane in range(8):
        oldfile=PARENT/f'lane{lane}.json'
        if file_sha(oldfile)!=parent['lane_sha256'][str(lane)]:
            raise ValueError('Parent frozen lane changed')
        original=read(oldfile);blocks=copy.deepcopy(original)
        lane_sizes[str(lane)]=len(blocks)
        for old,b in zip(original,blocks):
            for oldc,c in zip(old['base'],b['base']):
                raw=raw_by_asin[c['item']['asin']]
                if raw.get('average_rating')!=oldc['item'].get('average_rating'):
                    raise ValueError('Selected raw rating disagrees with parent item')
                c['item']=restore_raw_metadata(c['item'],raw)
                before={key:value for key,value in oldc['item'].items() if key not in EDITABLE_ITEM_FIELDS}
                after={key:value for key,value in c['item'].items() if key not in EDITABLE_ITEM_FIELDS}
                assert before==after
                assert {key:value for key,value in oldc.items() if key!='item'}=={key:value for key,value in c.items() if key!='item'}
                assert c['item'].get('options')==oldc['item'].get('options')
                for key in EDITABLE_ITEM_FIELDS:
                    if (key in oldc['item'])!=(key in c['item']) or oldc['item'].get(key)!=c['item'].get(key):
                        changed_fields[key]+=1
                # The repair must not change either detector's selection features.
                assert _page_text(oldc)==_page_text(c)
                assert structural_score(oldc['item'],oldc.get('reviews'))==structural_score(c['item'],c.get('reviews'))
            assert old['synthetics']==b['synthetics']
            assert {key:value for key,value in old.items() if key!='base'}=={key:value for key,value in b.items() if key!='base'}
            for c in b['base']+b['synthetics']:
                group='synthetic' if c['synthetic'] else 'real'
                rating,count=rating_and_count(c['item'])
                coverage[group]['instances']+=1
                coverage[group]['known_rating']+=rating is not None
                coverage[group]['known_review_count']+=count is not None
                f=product_fields(c['item'])
                assert f['rating']==(rating if rating is not None else 'n/a')
                assert f['nrev']==(count if count is not None else 'n/a')
                # Metadata changes must not change the reward for a fixed choice.
                env=SelectEnv(b['goal'],[copy.deepcopy(c)],n_candidates=1)
                env.step('select[1]')
                assert abs(env.reward()[0]-b['reward_by_cid'][c['cid']])<1e-9
                reward_checks+=1
            for rotation in ROTATIONS:
                clean=candidates(b,0,rotation);previous={}
                for k in COUNTS:
                    current=candidates(b,k,rotation)
                    oldcurrent=candidates(old,k,rotation)
                    assert [c['cid'] for c in current]==[c['cid'] for c in oldcurrent]
                    assert sum(a['cid']!=c['cid'] for a,c in zip(clean,current))==k
                    assert sum(c['kind']=='gold' for c in current)==1
                    for a,c in zip(clean,current):
                        if a['cid']==c['cid']:assert a==c
                    where={c['cid']:i for i,c in enumerate(current) if c['synthetic']}
                    assert all(where[cid]==pos for cid,pos in previous.items())
                    previous=where;checks+=1
                    page=results_page(current)
                    assert len(page)>0
                    page_checks+=1
            for k in COUNTS:
                ranks=collections.defaultdict(set)
                for rotation in ROTATIONS:
                    for rank,c in enumerate(candidates(b,k,rotation)):ranks[c['cid']].add(rank)
                assert all(len(v)==10 for v in ranks.values())
            if len(preview)<2:
                preview.append({'seed':b['seed'],'task_id':b['task_id'],
                    'goal':b['goal']['instruction_text'],'search_results':results_page(candidates(b,6,0))})
        write(DATA/f'lane{lane}.json',blocks)
    raw_coverage={'unique_real_products':len(raw_by_asin),
        'known_rating':sum(rating_and_count(p)[0] is not None for p in raw_by_asin.values()),
        'known_review_count':sum(rating_and_count(p)[1] is not None for p in raw_by_asin.values())}
    write(DATA/'metadata_audit.json',{'raw_coverage':raw_coverage,
        'block_candidate_coverage':{k:dict(v) for k,v in coverage.items()},
        'changed_field_instances':dict(changed_fields),'fixed_choice_reward_checks':reward_checks,
        'page_checks':page_checks,'slot_checks':checks,
        'only_real_item_fields_changed':sorted(EDITABLE_ITEM_FIELDS),
        'synthetic_candidates_byte_semantics_unchanged':True,'options_unchanged':True,
        'detector_features_unchanged':True,'parent_archive_sha256':file_sha(archive)})
    write(DATA/'input_previews.json',preview)
    sources=[p for p in (ROOT/'paired_sweep_ratingfix').rglob('*') if p.is_file() and p.suffix in ('.py','.md','.sbatch','.sh')]
    sources += [ROOT/'synthflood'/n for n in ('select_env.py','ws_loader.py','product_metadata.py','agent_react.py',
        'vllm_client.py','runlog.py','config.py','defenses.py','contaminate.py','metrics.py')]
    sources += [ROOT/'data/contamination'/n for n in ('goals100.json','pool.json')]
    sources += [ROOT/'m1/server_ready.py']
    sources += [ROOT/'.runtime/WebShop/web_agent_site/engine'/n for n in ('goal.py','normalize.py')]
    manifest=copy.deepcopy(parent)
    manifest.update(protocol='paired_sweep_ratingfix/PROTOCOL.md',arms=list(ARMS),
        main_rows=sum(lane_sizes.values())*40,defense_rows=sum(lane_sizes.values())*20*len(ARMS),
        main_rows_by_lane={k:v*40 for k,v in lane_sizes.items()},
        defense_rows_by_lane={k:v*20*len(ARMS) for k,v in lane_sizes.items()},
        lane_sha256={str(i):file_sha(DATA/f'lane{i}.json') for i in range(8)},
        source_sha256={str(p.relative_to(ROOT)):file_sha(p) for p in sources},
        parent_manifest_sha256=PARENT_MANIFEST_SHA,parent_input_directory=str(PARENT.relative_to(ROOT)),
        parent_source_archive_sha256=file_sha(archive),selected_raw_sha256=file_sha(DATA/'selected_raw.json'),
        metadata_audit_sha256=file_sha(DATA/'metadata_audit.json'),input_preview_sha256=file_sha(DATA/'input_previews.json'),
        metadata_policy='Recover existing raw average_rating and total_reviews; preserve genuine zero; missing stays n/a; no generated review bodies',
        parent_result_reuse='None; new services and freshly evaluated corrected main baseline',
        slot_invariant_checks=checks,fixed_choice_reward_checks=reward_checks,
        model_revision=REVISION)
    write(DATA/'manifest.json',manifest)
    print('RATINGFIX_N98_FROZEN',json.dumps({'main_rows':manifest['main_rows'],
        'defense_rows':manifest['defense_rows'],'arms':list(ARMS),'coverage':raw_coverage,
        'block_coverage':{k:dict(v) for k,v in coverage.items()},'slot_checks':checks,
        'reward_checks':reward_checks,'manifest_sha256':file_sha(DATA/'manifest.json')}),flush=True)


if __name__=='__main__':
    prepare()
