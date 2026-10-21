"""Use Hugging Face's parallel Rust range transfer on CPU nodes."""
import os
import time
import requests
from pathlib import Path
os.environ['HF_ENDPOINT']='https://hf-mirror.com'
os.environ['HF_HUB_ENABLE_HF_TRANSFER']='1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
os.environ['HF_HUB_ETAG_TIMEOUT']='60'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='60'
import hf_transfer

ROOT=Path(__file__).resolve().parents[1]


def download(repo, filename, directory, dataset=False):
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/filename
    if target.exists():
        return str(target)
    prefix='datasets/' if dataset else ''
    url=f'https://hf-mirror.com/{prefix}{repo}/resolve/main/{filename}?download=true'
    for attempt in range(8):
        try:
            response=requests.get(url,stream=True,timeout=(15,60),headers={'Accept-Encoding':'identity'})
            response.raise_for_status()
            size=int(response.headers.get('Content-Length',0))
            part=directory/(filename+'.fast.partial')
            if size>20*1024*1024:
                final_url=response.url
                response.close()
                hf_transfer.download(url=final_url,filename=str(part),max_files=32,
                    chunk_size=8*1024*1024,parallel_failures=8,max_retries=5)
            else:
                with response,part.open('wb') as f:
                    for chunk in response.iter_content(1024*1024):
                        f.write(chunk)
            if size and part.stat().st_size!=size:
                raise RuntimeError(f'Length mismatch for {filename}')
            if not size:
                # Small Hub JSON responses can use chunked HTTP without a
                # Content-Length. Validate the complete JSON before renaming.
                import json
                with part.open() as stream:
                    json.load(stream)
            part.rename(target)
            return str(target)
        except Exception as error:
            print('DOWNLOAD_RETRY',filename,attempt+1,type(error).__name__,str(error)[:180],flush=True)
            if attempt==7:
                raise
            time.sleep(60)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-only',action='store_true')
    args=parser.parse_args()
    if args.model_only:
        path=download('spacy/en_core_web_sm','en_core_web_sm-any-py3-none-any.whl',ROOT/'.runtime/spacy-model')
        import zipfile
        with zipfile.ZipFile(path) as archive:
            metadata=next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
            version=next(line.split(': ',1)[1] for line in archive.read(metadata).decode().splitlines() if line.startswith('Version: '))
        target=Path(path).with_name(f'en_core_web_sm-{version}-py3-none-any.whl')
        if not target.exists():
            Path(path).rename(target)
        print(target,flush=True)
    else:
        for filename in ('items_shuffle.json','items_ins_v2.json','items_human_ins.json'):
            print('START',filename,flush=True)
            path=download('YWZBrandon/webshop-data',filename,ROOT/'data/official',dataset=True)
            print('DOWNLOADED',path,Path(path).stat().st_size,flush=True)
