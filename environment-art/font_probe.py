"""Render unchanged Chinese fonts through SDL3_ttf at 2x and 3x for review.

The final comparison resizes these glyph images to a supplied display ratio.
It is an offline font sample, not a screenshot of VCMI's final compositing.
"""
import argparse,ctypes as C,ctypes.util,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw
class Color(C.Structure):_fields_=[(v,C.c_uint8) for v in ['r','g','b','a']]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fonts',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--display-scale',type=float,default=2.72);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a new output directory')
 a.out.mkdir(parents=True);sdl=C.CDLL(ctypes.util.find_library('SDL3') or '/opt/homebrew/lib/libSDL3.dylib');ttf=C.CDLL(ctypes.util.find_library('SDL3_ttf') or '/opt/homebrew/lib/libSDL3_ttf.dylib')
 def signature(lib,name,result,*args):f=getattr(lib,name);f.restype=result;f.argtypes=list(args);return f
 init=signature(ttf,'TTF_Init',C.c_bool);op=signature(ttf,'TTF_OpenFont',C.c_void_p,C.c_char_p,C.c_float);hint=signature(ttf,'TTF_SetFontHinting',None,C.c_void_p,C.c_int);render=signature(ttf,'TTF_RenderText_Blended',C.c_void_p,C.c_void_p,C.c_char_p,C.c_size_t,Color);save=signature(sdl,'SDL_SaveBMP',C.c_bool,C.c_void_p,C.c_char_p);destroy=signature(sdl,'SDL_DestroySurface',None,C.c_void_p);close=signature(ttf,'TTF_CloseFont',None,C.c_void_p)
 assert init();records=[];result=Image.new('RGB',(1500,600),(31,34,39));draw=ImageDraw.Draw(result)
 rows=[('SIMLI.TTF',22,'墓园城镇  英雄无敌'),('WenQuanYi.ttf',13,'吸血鬼王  攻击  防御  生命值'),('WenQuanYi.ttf',9,'1234567890  数量  伤害  速度')]
 for col,scale in enumerate([2,3]):
  draw.text((col*750+20,16),f'{scale}x glyphs -> {a.display_scale:.2f}x display (same fonts / logical sizes)',fill='white')
  for row,(name,size,text) in enumerate(rows):
   f=op(str(a.fonts/name).encode(),size*scale);assert f;hint(f,2);raw=text.encode();surface=render(f,raw,len(raw),Color(245,231,186,255));assert surface
   path=a.out/f'{name}-{scale}x-{size}.bmp';assert save(surface,str(path).encode());destroy(surface);close(f)
   im=Image.open(path).convert('RGBA');im.save(path.with_suffix('.png'));display=im.resize((round(im.width*a.display_scale/scale),round(im.height*a.display_scale/scale)),Image.Resampling.BILINEAR);result.paste(display,(col*750+20,60+row*160),display)
   records.append(dict(font=name,sourceSHA256=hashlib.sha256((a.fonts/name).read_bytes()).hexdigest(),logicalSize=size,rasterScale=scale,rasterSize=im.size))
 result.save(a.out/'comparison.png');(a.out/'audit.json').write_text(json.dumps({'displayScale':a.display_scale,'renderer':'SDL3_ttf blended, monochrome hinting as in local VCMI; offline bilinear final resize','fontFilesChanged':False,'samples':records},indent=2)+'\n')
if __name__=='__main__':main()
