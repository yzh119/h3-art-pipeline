#!/usr/bin/env python3
"""Publish offline review videos from installed-style creature resources.

Requires Pillow and ffmpeg. Uses native frame counts at explicit review rates;
these composites are not native game captures or runtime timing measurements.
"""
import argparse
import html
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw
from vcmi_anim import GROUP_NAMES


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mod',type=Path,required=True)
    p.add_argument('--unit',action='append',required=True,help='CWIGHT=EXPORT_DIRECTORY=Display name')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--title',required=True)
    p.add_argument('--panel-top',type=int,default=310,help='Fixed showcase crop top in 2x canvas pixels')
    p.add_argument('--double-wide',action='append',default=[],help='Creature whose native panel starts at logical x=170 instead of 150')
    args=p.parse_args()
    if args.out.exists():raise ValueError('Use a fresh preview directory')
    args.out.mkdir(parents=True)
    background=Image.open(args.mod/'content/Data2x/CRBKGNEC.png').convert('RGBA')
    cards=[];reports=[]
    for spec in args.unit:
        cid,directory,label=spec.split('=',2);cid=cid.upper();directory=Path(directory)
        report=json.loads((directory/'manifest.json').read_text())
        if report.get('previewOnly'):raise ValueError('Incomplete probe export')
        folder=args.mod/'content/Sprites2x/creatures'/cid.lower()
        panel_left=340 if cid in {name.upper() for name in args.double_wide} else 300
        def composite(name,wide=False):
            # Both are fixed crops. No per-frame recentering or resizing.
            box=(200,250,700,650) if wide else (panel_left,args.panel_top,panel_left+200,args.panel_top+260)
            canvas=Image.new('RGBA',(900,800),(45,49,54,255))
            if not wide:canvas.alpha_composite(background,(panel_left,args.panel_top))
            for suffix in ['-shadow','']:
                image=Image.open(folder/(name+suffix+'.png')).convert('RGBA')
                canvas.alpha_composite(image)
            return canvas.crop(box).convert('RGB')
        composite('holding_00').save(args.out/(cid.lower()+'-showcase.png'))
        sheet=Image.new('RGB',(1000,800),(45,49,54));draw=ImageDraw.Draw(sheet)
        for i,group in enumerate(['HOLDING','MOVING','ATTACK_FRONT','DEATH']):
            clip=report['clips'][group];idx=len(clip['frames'])-1 if group=='DEATH' else len(clip['frames'])//2
            name=Path(clip['frames'][idx]['file']).stem
            sheet.paste(composite(name,True),((i%2)*500,(i//2)*400))
            draw.text(((i%2)*500+12,(i//2)*400+12),group,fill='white')
        sheet.save(args.out/(cid.lower()+'-poses.png'))
        figures=[]
        for group,clip in report['clips'].items():
            filename=cid.lower()+'-'+group.lower()+'.mp4';fps=4 if group=='HOLDING' else 8
            with tempfile.TemporaryDirectory(prefix='vcmi-preview-') as temp:
                for i,frame in enumerate(clip['frames']):composite(Path(frame['file']).stem,True).save(Path(temp)/f'{i:03}.png')
                subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(fps),'-i',str(Path(temp)/'%03d.png'),
                                '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(args.out/filename)],check=True)
            figures.append(f'<figure><figcaption>{group} · {len(clip["frames"])} frames</figcaption><video controls loop muted playsinline preload="none" src="{filename}"></video></figure>')
        cards.append(f'<h2>{html.escape(label)}</h2><img width="200" height="260" src="{cid.lower()}-showcase.png" alt="Showcase crop"><div class="grid">'+''.join(figures)+'</div>')
        reports.append({'creature':cid,'panelCrop2x':[panel_left,args.panel_top,200,260],'clips':{k:{'frames':len(v['frames']),'seconds':v.get('seconds'),'loop':v.get('loop')} for k,v in report['clips'].items()},'checks':report.get('checks')})
    (args.out/'measurements.json').write_text(json.dumps(reports,indent=2)+'\n')
    (args.out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'''+html.escape(args.title)+'''</title><style>body{max-width:1100px;margin:32px auto;padding:16px;background:#15191e;color:#eee;font:16px system-ui}a{color:#9bd4ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}figure{margin:0}video{width:100%;max-width:500px}</style><h1>'''+html.escape(args.title)+'''</h1><p>按固定画布离线合成，并非游戏截图。待机 4 fps，其余 8 fps，供审阅，不代表游戏速度。展示图使用游戏背景，动作视频使用灰底以便查看轮廓。</p><p>Fixed-canvas offline composites, not game captures. Holding: 4 fps; other clips: 8 fps for review, independently of runtime timing. Still showcases use the installed background; motion videos use gray for silhouette inspection.</p><p><a href="measurements.json">Measurements</a> · <a href="validation.json">Validation</a></p>'''+''.join(cards)+'</html>')
    print(args.out)


if __name__=='__main__':main()
