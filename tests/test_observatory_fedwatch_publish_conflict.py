import json,sys,tempfile,subprocess,copy,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import publish_observatory_data as pub
from archive_fedwatch import archive_snapshot
snapshot={'schema':'JJOONI_FED_WATCH_V1','contains_account_data':False,'read_only':True,'market_data_as_of':'2026-10-09','meeting_probability_matrix':[{'meeting_date':'2026-10-28','probabilities':{'3.50-3.75':0.8,'3.75-4.00':0.2}}],'freshness':'LIVE','source':'Regression fixture'}
def git(root,*args):
 return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
def setup(root):
 git(root,'config','user.name','Regression');git(root,'config','user.email','regression@example.test')
def write(root,stamp):
 data=root/'market-observatory/data';data.mkdir(parents=True,exist_ok=True)
 s=copy.deepcopy(snapshot);s['generated_kst']=stamp
 (data/'fed-watch.json').write_text(json.dumps(s))
 archive_snapshot(s,data)
 return ['market-observatory/data/fed-watch.json']+[str(p.relative_to(root)) for p in (data/'fedwatch-history').rglob('*') if p.is_file()]

class FedWatchPublicationConflictTest(unittest.TestCase):
    def test_concurrent_snapshot_and_generated_views_are_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
         root=Path(tmp);bare=root/'remote.git';remote=root/'producer';local=root/'daily'
         subprocess.run(['git','init','--bare',str(bare)],check=True,capture_output=True)
         subprocess.run(['git','clone',str(bare),str(remote)],check=True,capture_output=True);setup(remote)
         git(remote,'checkout','-b','main');write(remote,'2026-10-13T10:00:00+09:00');git(remote,'add','.');git(remote,'commit','-m','base');git(remote,'push','origin','main')
         subprocess.run(['git','clone','-b','main',str(bare),str(local)],check=True,capture_output=True);setup(local)
         paths=write(local,'2026-10-13T11:00:00+09:00')
         write(remote,'2026-10-13T12:00:00+09:00');git(remote,'add','.');git(remote,'commit','-m','concurrent market refresh');git(remote,'push','origin','main')
         with patch.object(pub,'ROOT',local):pub.publish(paths,'daily after concurrent market refresh')
         index=json.loads((local/'market-observatory/data/fedwatch-history/index.json').read_text())
         entry=next(e for e in index['entries'] if e['market_data_as_of']==snapshot['market_data_as_of'])
         assert len(entry['revisions'])==3,entry
         assert json.loads((local/'market-observatory/data/fed-watch.json').read_text())['generated_kst']=='2026-10-13T12:00:00+09:00'
         assert '2026-10-13T12:00:00+09:00' in (local/'market-observatory/data/fedwatch-history/brief.md').read_text()
         assert '2026-10-13T12:00:00+09:00' in (local/'market-observatory/data/fedwatch-history/probabilities.csv').read_text()
         assert not git(local,'status','--porcelain')
         # One publication = one commit; the post-rebase re-derivation is folded in.
         subjects=git(bare,'log','main','--format=%s').splitlines()
         assert subjects==['daily after concurrent market refresh','concurrent market refresh','base'],subjects
         print('FEDWATCH_REAL_GIT_CONFLICT_RECOVERY=PASS revisions=3 newer_snapshot_preserved views_regenerated clean_worktree')
