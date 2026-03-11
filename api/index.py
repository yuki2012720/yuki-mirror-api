from flask import Flask, request, send_file
from flask_cors import CORS
from PIL import Image, ImageOps, ImageSequence
import io

app = Flask(__name__)
CORS(app) # 允许你的 Hexo 博客跨域访问

def process_frame(img, mode):
    w, h = img.size
    # 使用 RGBA 模式处理，防止透明背景变黑
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    
    if mode == 'left-right':
        half_w = w // 2
        part = img.crop((0, 0, half_w, h))
        mirror = ImageOps.mirror(part)
        canvas.paste(part, (0, 0))
        canvas.paste(mirror, (w - half_w, 0))
    elif mode == 'right-left':
        half_w = w // 2
        part = img.crop((w - half_w, 0, w, h))
        mirror = ImageOps.mirror(part)
        canvas.paste(mirror, (0, 0))
        canvas.paste(part, (w - half_w, 0))
    elif mode == 'top-bottom':
        half_h = h // 2
        part = img.crop((0, 0, w, half_h))
        mirror = ImageOps.flip(part)
        canvas.paste(part, (0, 0))
        canvas.paste(mirror, (0, h - half_h))
    elif mode == 'bottom-top':
        half_h = h // 2
        part = img.crop((0, h - half_h, w, h))
        mirror = ImageOps.flip(part)
        canvas.paste(mirror, (0, 0))
        canvas.paste(part, (0, h - half_h))
    return canvas

@app.route('/mirror', methods=['POST'])
def mirror():
    if 'image' not in request.files:
        return "No image uploaded", 400
    
    file = request.files['image']
    mode = request.form.get('mode', 'left-right')
    
    img = Image.open(file)
    output = io.BytesIO()

    # 如果是 GIF，遍历每一帧处理
    if getattr(img, "is_animated", False):
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(img):
            new_frame = process_frame(frame.convert("RGBA"), mode)
            frames.append(new_frame)
            durations.append(frame.info.get('duration', 100))
        
        frames[0].save(
            output, 
            format='GIF', 
            save_all=True, 
            append_images=frames[1:], 
            loop=0, 
            duration=durations,
            disposal=2 # 清理背景，防止重影
        )
    else:
        # 普通图片处理
        processed = process_frame(img.convert("RGBA"), mode)
        processed.save(output, format='PNG')

    output.seek(0)
    mime = 'image/gif' if getattr(img, "is_animated", False) else 'image/png'
    return send_file(output, mimetype=mime)

# 必须导出这个 app 供 Vercel 使用
