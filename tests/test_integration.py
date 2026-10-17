"""Offline contracts, real CLI/file I/O, local HTTP, and relocatable bundles.

Fake transports below are explicitly mocks, NOT live detector/model scores.
"""
import contextlib
import copy
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from clearwrite import cli
from clearwrite.core import InputError,analyze,apply_plan,make_plan,text_hash
from clearwrite.io import read_text,write_text,strict_json,read_json,ensure_destination
from clearwrite.providers import ProviderError,ollama_plan,NoRedirect,request_json
from clearwrite.ui import Server


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
INSTALL=module(ROOT/'scripts/install_codex.py','install_clearwrite')
PUBLISH=module(ROOT/'scripts/publish_github.py','publish_clearwrite')
TEXT='이와 같은 표현을 사용하여 문서의 내용을 확인한다. 원본 파일은 별도로 보관한다.'


class ProviderTests(unittest.TestCase):
    def test_redirect_rejected(self):
        with self.assertRaises(ProviderError):NoRedirect().redirect_request(None,None,302,'',{},'https://evil.invalid')
    def test_transport_timeout_bounds(self):
        with self.assertRaises(InputError):request_json('GET','https://invalid.test',{},None,999)
    def test_ollama_plan_real_parser(self):
        calls=[]
        def tx(*args):
            calls.append(args);return {'message':{'content':json.dumps({'schema_version':'1.0','source_sha256':text_hash(TEXT),'edits':[{'original':'이와 같은','replacement':'이런','reason':'간결화','rule':'KO01'}]},ensure_ascii=False)}}
        plan=ollama_plan(TEXT,model='test:small',transport=tx)
        self.assertEqual(apply_plan(TEXT,plan)['status'],'edited');self.assertEqual(calls[0][1],'http://127.0.0.1:11434/api/chat')
        self.assertNotIn('tools',calls[0][3]);self.assertFalse(calls[0][3]['stream']);self.assertIsInstance(calls[0][3]['format'],dict)
    def test_ollama_selector_restrictions(self):
        for name in ['../x','x/../y','https://other','model-cloud','test;rm','',None]:
            with self.subTest(name=name),self.assertRaises(InputError):ollama_plan(TEXT,model=name,transport=lambda *a:self.fail('network'))
    def test_ollama_bad_port(self):
        for port in [80,70000,True,'11434']:
            with self.subTest(port=port),self.assertRaises(InputError):ollama_plan(TEXT,model='test',port=port)
    def test_ollama_non_json(self):
        with self.assertRaises(ProviderError):ollama_plan(TEXT,model='test',transport=lambda *a:{'message':{'content':'not a plan'}})
    def test_ollama_missing_message(self):
        with self.assertRaises(ProviderError):ollama_plan(TEXT,model='test',transport=lambda *a:{})
    def test_ollama_ambiguous_output(self):
        text='이와 같은 예. 이와 같은 글.'
        p={'schema_version':'1.0','source_sha256':text_hash(text),'edits':[{'original':'이와 같은','replacement':'이런','reason':'r','rule':'x'}]}
        with self.assertRaises(InputError):ollama_plan(text,model='test',transport=lambda *a:{'message':{'content':json.dumps(p)}})


class IOCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='맑은글 space ');self.root=Path(self.temp.name);self.input=self.root/'한글 원문.txt';self.input.write_text(TEXT,encoding='utf-8')
    def tearDown(self):self.temp.cleanup()
    def run_cli(self,*args,stdin=None):
        e=os.environ.copy()
        return subprocess.run([sys.executable,str(ROOT/'rewrite.py'),*map(str,args)],input=stdin,text=True,encoding='utf-8',capture_output=True,timeout=15,env=e)
    def test_file_rewrite(self):
        out=self.root/'다듬은 글.txt';report=self.root/'검수.json';r=self.run_cli('rewrite',self.input,'-o',out,'--report',report)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.input.read_text(encoding='utf-8'),TEXT)
        self.assertIn('이런',out.read_text(encoding='utf-8'));self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['status'],'edited')
    def test_standard_input(self):
        r=self.run_cli('analyze','-',stdin=TEXT);self.assertEqual(r.returncode,0);self.assertIsNone(json.loads(r.stdout)['ai_probability'])
    def test_doctor_no_secrets(self):
        r=self.run_cli('doctor');self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['network_requests'],0)
    def test_no_input_clobber_even_force(self):
        r=self.run_cli('rewrite',self.input,'-o',self.input,'--force');self.assertEqual(r.returncode,3);self.assertEqual(self.input.read_text(encoding='utf-8'),TEXT)
    def test_no_report_output_collision(self):
        out=self.root/'same.txt';r=self.run_cli('rewrite',self.input,'-o',out,'--report',out);self.assertEqual(r.returncode,3);self.assertFalse(out.exists())
    def test_no_overwrite_default(self):
        out=self.root/'result.txt';out.write_text('KEEP',encoding='utf-8');r=self.run_cli('rewrite',self.input,'-o',out)
        self.assertEqual(r.returncode,3);self.assertEqual(out.read_text(),'KEEP')
    def test_explicit_output_replace(self):
        out=self.root/'result.txt';out.write_text('OLD');r=self.run_cli('rewrite',self.input,'-o',out,'--force');self.assertEqual(r.returncode,0)
    def test_verify_failure_exit(self):
        p=self.root/'a.txt';q=self.root/'b.txt';p.write_text('표본은 30명이다.',encoding='utf-8');q.write_text('표본은 31명이다.',encoding='utf-8')
        r=self.run_cli('verify',p,q);self.assertEqual(r.returncode,2);self.assertFalse(json.loads(r.stdout)['passed'])
    def test_preserve_never_calls_ollama(self):
        r=self.run_cli('rewrite',self.input,'--backend','ollama','--mode','preserve');self.assertEqual(r.returncode,0);self.assertEqual(r.stdout.rstrip('\n'),TEXT)
    def test_builtin_voice_not_silently_ignored(self):
        r=self.run_cli('rewrite',self.input,'--voice',self.input);self.assertEqual(r.returncode,3)
    def test_proposal_roundtrip(self):
        props=self.root/'p.json';props.write_text(json.dumps({'schema_version':'1.0','source_sha256':text_hash(TEXT),'edits':[{'original':'이와 같은','replacement':'이런','reason':'r','rule':'KO01'}]},ensure_ascii=False),encoding='utf-8')
        r=self.run_cli('apply',self.input,'--proposals',props);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('이런',r.stdout)
    def test_prepare_offset_free(self):
        r=self.run_cli('prepare',self.input,'--proposals');self.assertEqual(r.returncode,0);self.assertNotIn('start',json.loads(r.stdout)['output_schema']['properties']['edits']['items']['properties'])
    def test_bom_and_crlf_preserved(self):
        p=self.root/'crlf.txt';p.write_bytes(b'\xef\xbb\xbf'+TEXT.encode()+b'\r\n');self.assertEqual(read_text(str(p)),TEXT+'\r\n')
    def test_invalid_utf8_error(self):
        self.input.write_bytes(b'\xff');r=self.run_cli('analyze',self.input);self.assertEqual(r.returncode,3);self.assertNotIn('Traceback',r.stderr)
    def test_large_file(self):
        self.input.write_text('a'*12001);self.assertEqual(self.run_cli('analyze',self.input).returncode,3)
    def test_missing_parent(self):
        with self.assertRaises(InputError):write_text(str(self.root/'missing/a.txt'),'text')
    def test_json_duplicate_on_disk(self):
        p=self.root/'p.json';p.write_text('{"edits":[],"edits":[]}')
        with self.assertRaises(InputError):read_json(str(p))
    def test_symlink_output(self):
        p=self.root/'link'
        try:p.symlink_to(self.input)
        except OSError:self.skipTest('symlink unavailable on this host')
        with self.assertRaises(InputError):write_text(str(p),'bad',force=True)


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=Server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join(3)
    def request(self,method='GET',path='/',body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        h={'Origin':self.server.origin,'Content-Type':'application/json','X-ClearWrite-Token':self.server.token};h.update(headers or {})
        if isinstance(body,dict):body=json.dumps(body).encode()
        c.request(method,path,body=body,headers=h);r=c.getresponse();result=(r.status,dict(r.getheaders()),r.read().decode('utf-8'));c.close();return result
    def test_page_security_headers(self):
        status,h,b=self.request();self.assertEqual(status,200);self.assertEqual(h['Cache-Control'],'no-store');self.assertEqual(h['X-Frame-Options'],'DENY');self.assertIn("default-src 'none'",h['Content-Security-Policy']);self.assertNotIn('__TOKEN__',b)
    def test_rewrite(self):
        s,h,b=self.request('POST','/api/process',{'action':'rewrite','text':TEXT});self.assertEqual(s,200,b);self.assertEqual(json.loads(b)['status'],'edited')
    def test_analyze(self):
        s,h,b=self.request('POST','/api/process',{'action':'analyze','text':TEXT});self.assertEqual(s,200);self.assertIsNone(json.loads(b)['ai_probability'])
    def test_cross_origin(self):
        s,h,b=self.request('POST','/api/process',{'action':'analyze','text':TEXT},{'Origin':'https://evil.invalid'});self.assertEqual(s,403)
    def test_bad_host(self):self.assertEqual(self.request(headers={'Host':'evil.invalid'})[0],403)
    def test_bad_token(self):self.assertEqual(self.request('POST','/api/process',{'text':TEXT},{'X-ClearWrite-Token':'wrong'})[0],403)
    def test_unexpected_path(self):self.assertEqual(self.request(path='/../../etc/passwd')[0],404)
    def test_wrong_content_type(self):self.assertEqual(self.request('POST','/api/process','text',{'Content-Type':'text/plain'})[0],415)
    def test_json_bad_types(self):
        for data in [{'action':'rewrite','text':TEXT,'mode':[]},{'action':'analyze','text':[]},{'action':'execute','text':TEXT},{'action':'analyze','text':TEXT,'secret':'x'}]:
            with self.subTest(data=data):self.assertEqual(self.request('POST','/api/process',data)[0],400)
    def test_json_invalid(self):self.assertEqual(self.request('POST','/api/process','{"bad":')[0],400)
    def test_big_request(self):self.assertEqual(self.request('POST','/api/process','a'*100001)[0],413)
    def test_preserve_skips_ollama(self):
        s,h,b=self.request('POST','/api/process',{'action':'rewrite','text':TEXT,'mode':'preserve','backend':'ollama'});self.assertEqual(s,200);self.assertEqual(json.loads(b)['text'],TEXT)
    def test_html_is_data(self):
        text='<script>alert("test")</script>\n도구를 사용하여 문서를 읽는다.'
        s,h,b=self.request('POST','/api/process',{'action':'rewrite','text':text});self.assertEqual(s,200);self.assertIn('<script>',json.loads(b)['text']);self.assertTrue(h['Content-Type'].startswith('application/json'))


class BundleInstallTests(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory(prefix='clearwrite home ');self.home=Path(self.t.name)
    def tearDown(self):self.t.cleanup()
    def test_dry_run_no_mutation(self):
        r=INSTALL.install(home=self.home);self.assertEqual(r['mode'],'dry-run');self.assertEqual(list(self.home.iterdir()),[])
    def test_skill_install_and_relocate(self):
        r=INSTALL.install(home=self.home,apply=True);p=Path(r['destination'])/'scripts/clearwrite_skill.py';self.assertTrue(p.exists())
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        proc=subprocess.run([sys.executable,str(p),'analyze','-'],cwd=self.home,input=TEXT,text=True,encoding='utf-8',capture_output=True,env=env,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr);self.assertIn('ai_style_score',json.loads(proc.stdout))
    def test_idempotent(self):
        INSTALL.install(home=self.home,apply=True);r=INSTALL.install(home=self.home,apply=True);self.assertEqual(r['status'],'already-current');self.assertEqual(r['backups'],[])
    def test_requires_replace_and_backup(self):
        r=INSTALL.install(home=self.home,apply=True);p=Path(r['destination'])/'SKILL.md';p.write_text('custom')
        with self.assertRaises(ValueError):INSTALL.install(home=self.home,apply=True)
        r=INSTALL.install(home=self.home,apply=True,replace=True);self.assertEqual((Path(r['backups'][0])/'SKILL.md').read_text(),'custom')
    def test_plugin_catalog(self):
        r=INSTALL.install(kind='plugin',home=self.home,apply=True);j=json.loads(Path(r['catalog']).read_text(encoding='utf-8'));self.assertEqual(j['plugins'][0]['source']['path'],'./.codex/plugins/clearwrite')
    def test_preserves_other_catalog_entries(self):
        p=self.home/'.agents/plugins/marketplace.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'name':'mine','plugins':[{'name':'other','source':{'source':'local','path':'./other'}}]}))
        INSTALL.install(kind='plugin',home=self.home,apply=True);j=json.loads(p.read_text());self.assertEqual(j['name'],'mine');self.assertEqual(j['plugins'][0]['name'],'other');self.assertEqual(len(j['plugins']),2)
    def test_project_paths(self):
        r=INSTALL.install(kind='plugin',project=self.home,apply=True);self.assertEqual(r['destination'],str(self.home/'plugins/clearwrite'))
    def test_catalog_collision_rejected(self):
        p=self.home/'.agents/plugins/marketplace.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'name':'x','plugins':[{'name':'clearwrite','source':{'source':'local','path':'./other'}}]}))
        with self.assertRaises(ValueError):INSTALL.install(kind='plugin',home=self.home,apply=True)
        self.assertFalse((self.home/'.codex').exists())
    def test_symlink_install_path(self):
        real=self.home/'real';real.mkdir();link=self.home/'.agents'
        try:link.symlink_to(real,target_is_directory=True)
        except OSError:self.skipTest('symlink unavailable')
        with self.assertRaises(ValueError):INSTALL.install(home=self.home,apply=True)
    def test_bundles_exact(self):
        expected=json.loads((ROOT/'data/bundle-source-hashes.json').read_text())
        for filename,digest in expected.items():
            for base in ['src/clearwrite','skills/clearwrite/scripts/clearwrite','plugins/clearwrite/skills/clearwrite/scripts/clearwrite']:
                self.assertEqual(hashlib.sha256((ROOT/base/filename).read_bytes()).hexdigest(),digest,(base,filename))
    def test_manifests(self):
        j=json.loads((ROOT/'plugins/clearwrite/plugin.json').read_text(encoding='utf-8'));o=json.loads((ROOT/'plugins/clearwrite/.codex-plugin/plugin.json').read_text(encoding='utf-8'));self.assertEqual(j['name'],o['name']);self.assertEqual(j['version'],o['version']);self.assertEqual(o['skills'],'./skills/');self.assertNotIn('mcpServers',j)
    def test_no_global_config_changes(self):
        config=self.home/'.codex/config.toml';config.parent.mkdir();config.write_text('unrelated = true\n')
        INSTALL.install(home=self.home,apply=True);self.assertEqual(config.read_text(),'unrelated = true\n')
    def test_publish_plan_no_writes(self):
        for filename in ['README.md','LICENSE','pyproject.toml']:(self.home/filename).write_text('safe')
        before=list(self.home.iterdir());p=PUBLISH.make_plan('clearwrite',self.home);self.assertEqual(p['file_count'],3);self.assertEqual(before,list(self.home.iterdir()))
    def test_publish_rejects_names_and_existing_git(self):
        for name in ['-bad','../bad','x/y/z','x;curl']:
            with self.subTest(name=name),self.assertRaises(ValueError):PUBLISH.make_plan(name,self.home)
        (self.home/'.git').mkdir()
        with self.assertRaises(ValueError):PUBLISH.make_plan('clearwrite',self.home)
    def test_publish_secret_detection(self):
        for filename in ['README.md','LICENSE','pyproject.toml']:(self.home/filename).write_text('safe')
        (self.home/'README.md').write_text('ghp_'+'A'*30)
        with self.assertRaises(ValueError):PUBLISH.make_plan('clearwrite',self.home)


class NewRegressionTests(unittest.TestCase):
    def test_long_quote(self):
        text='He said "'+('a '*1600)+'in order to finish". Outside.'
        self.assertEqual(make_plan(text)['edits'],[])
    def test_multiline_quote(self):
        text='He said "a\nin order to finish".'
        self.assertEqual(make_plan(text)['edits'],[])
    def test_bad_mode_types(self):
        for mode in [None,{},[],True]:
            with self.subTest(mode=mode),self.assertRaises(InputError):make_plan(TEXT,mode=mode)

if __name__=='__main__':unittest.main()
