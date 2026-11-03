#!/usr/bin/env python3
"""Bounded yt-dlp collection with per-run evidence and explicit outcomes."""
import argparse, json, subprocess, sys, pathlib, datetime, re, uuid

def positive(s):
 n=int(s)
 if not 1 <= n <= 100: raise argparse.ArgumentTypeError('limit must be 1..100')
 return n

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('inputs',nargs='+',help='URLs or ytsearchN:query'); p.add_argument('--out',required=True)
 p.add_argument('--limit',type=positive,default=1); p.add_argument('--subtitles',action='store_true')
 p.add_argument('--languages',default='zh.*,en.*'); p.add_argument('--audio',action='store_true'); p.add_argument('--format',default='bestaudio/best')
 a=p.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
 run=out/('run-'+uuid.uuid4().hex[:12]); run.mkdir()
 manifest={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run':run.name,'items':[]}
 def save():
  tmp=out/'manifest.json.tmp'; tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8'); tmp.replace(out/'manifest.json')
 def execute(cmd,timeout):
  try:
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout); return r.returncode,r.stdout,r.stderr
  except (subprocess.TimeoutExpired,OSError) as e: return 1,'',str(e)
 seen=set(); failed=False; save()
 for url in a.inputs:
  base=[sys.executable,'-m','yt_dlp','--ignore-config','--no-warnings','--socket-timeout','15','--retries','1','--playlist-end',str(a.limit)]
  if a.limit==1 and not url.startswith('ytsearch'): base+=['--no-playlist']
  code,stdout,stderr=execute(base+['--dump-single-json','--skip-download',url],120)
  if code:
   failed=True; manifest['items'].append({'input':url,'status':'metadata_failed','error':stderr[-2000:]}); save(); continue
  try: data=json.loads(stdout)
  except ValueError:
   failed=True; manifest['items'].append({'input':url,'status':'metadata_invalid'}); save(); continue
  entries=data.get('entries') if data.get('_type') in ('playlist','multi_video') else [data]
  for entry in (entries or [])[:a.limit]:
   if not entry: continue
   key=(entry.get('extractor_key') or entry.get('extractor'),entry.get('id'))
   if key in seen: continue
   seen.add(key)
   fields=('id','title','webpage_url','extractor','uploader','upload_date','duration','description','chapters','view_count')
   item={k:entry.get(k) for k in fields}; item.update(input=url,status='metadata_only',subtitle_status='not_requested',audio_status='not_requested',subtitle_files=[],audio_files=[])
   manifest['items'].append(item); save()
   if a.subtitles or a.audio:
    safe=re.sub(r'[^A-Za-z0-9_.-]','_',str(key[0] or 'unknown')+'_'+str(key[1] or uuid.uuid4().hex))
    d=run/safe; d.mkdir(exist_ok=True)
    args=base+['--no-playlist','-o',str(d/'%(id)s.%(ext)s')]
    if a.subtitles: args+=['--write-subs','--write-auto-subs','--sub-langs',a.languages,'--sub-format','vtt/srt/best']
    if not a.audio: args+=['--skip-download']
    else: args+=['-f',a.format,'--continue','--download-archive',str(out/'archive.txt')]
    code,stdout,stderr=execute(args+[entry.get('webpage_url') or url],180)
    subext={'.vtt','.srt','.ttml','.ass','.srv1','.srv2','.srv3','.json3'}
    files=[f for f in d.iterdir() if f.is_file() and not f.name.endswith(('.part','.ytdl'))]
    item['subtitle_files']=[str(f.relative_to(out)) for f in files if f.suffix.lower() in subext]
    item['audio_files']=[str(f.relative_to(out)) for f in files if f.suffix.lower() not in subext and not f.name.endswith(('.json','.description'))]
    if a.subtitles: item['subtitle_status']='collected' if item['subtitle_files'] else 'not_obtained'
    if a.audio: item['audio_status']='collected' if item['audio_files'] else ('archive_skipped' if 'already been recorded in the archive' in stdout else 'not_obtained')
    ok=not code and (not a.subtitles or item['subtitle_files']) and (not a.audio or item['audio_files'])
    item['status']='collected' if ok else 'content_incomplete'
    if not ok: failed=True; item['error']=stderr[-2000:] or 'Requested content not obtained in this run; see individual statuses.'
    save()
 print('Manifest:',out/'manifest.json'); return 1 if failed else 0
if __name__=='__main__': sys.exit(main())
