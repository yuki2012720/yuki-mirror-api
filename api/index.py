from flask import Flask, request, send_file
from flask_cors import CORS
from PIL import Image, ImageOps, ImageSequence
import io
import math
import numpy as np
import random

app = Flask(__name__)
CORS(app)

def process_frame(img, mode):
    w, h = img.size
    # 使用 RGBA 模式处理，防止透明背景变黑
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    
    if mode == 'left-right':
        mid = (w + 1) // 2  # 向上取整，多取 1 像素覆盖中线
        part = img.crop((0, 0, mid, h))
        mirror = ImageOps.mirror(part)
        canvas.paste(part, (0, 0))
        canvas.paste(mirror, (w - mid, 0)) # 完美对齐起点
    elif mode == 'right-left':
        mid = (w + 1) // 2
        part = img.crop((w - mid, 0, w, h))
        mirror = ImageOps.mirror(part)
        canvas.paste(mirror, (0, 0))
        canvas.paste(part, (w - mid, 0))
    elif mode == 'top-bottom':
        mid = (h + 1) // 2
        part = img.crop((0, 0, w, mid))
        mirror = ImageOps.flip(part)
        canvas.paste(part, (0, 0))
        canvas.paste(mirror, (0, h - mid))
    elif mode == 'bottom-top':
        mid = (h + 1) // 2
        part = img.crop((0, h - mid, w, h))
        mirror = ImageOps.flip(part)
        canvas.paste(mirror, (0, 0))
        canvas.paste(part, (0, h - mid))
    return canvas

@app.route('/mirror', methods=['POST'])
def mirror():
    if 'image' not in request.files:
        return "No image uploaded", 400
    
    file = request.files['image']
    mode = request.form.get('mode', 'left-right')
    
    img = Image.open(file)
    output = io.BytesIO()

    if getattr(img, "is_animated", False):
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(img):
            # convert("RGBA") 确保每一帧都能正常拼合
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
            disposal=2 
        )
    else:
        processed = process_frame(img.convert("RGBA"), mode)
        processed.save(output, format='PNG')

    output.seek(0)
    mime = 'image/gif' if getattr(img, "is_animated", False) else 'image/png'
    return send_file(output, mimetype=mime)

# Vercel 要求的导出
app = app
@app.route('/shuffle', methods=['POST'])
def pixel_shuffle():
    if 'image' not in request.files:
        return "No image uploaded", 400
    
    file = request.files['image']
    img = Image.open(file)
    
    # 块大小：越小越碎，越鬼畜
    block_size = int(request.form.get('block_size', 20))
    block_size = max(5, min(200, block_size)) # 限制范围防止崩溃
    
    frames = []
    durations = []
    
    # 获取 GIF 的每一帧
    for frame in ImageSequence.Iterator(img):
        f = frame.convert("RGBA")
        w, h = f.size
        
        # 计算可以切分多少块
        nx, ny = w // block_size, h // block_size
        if nx == 0 or ny == 0:
            return "Block size too large for this image", 400
            
        # 1. 采集所有的像素块
        blocks = []
        for j in range(ny):
            for i in range(nx):
                box = (i * block_size, j * block_size, (i + 1) * block_size, (j + 1) * block_size)
                blocks.append(f.crop(box))
        
        # 2. 暴力洗牌（每一帧都乱序，产生闪烁感）
        random.shuffle(blocks)
        
        # 3. 重新拼装回新画布
        new_f = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        idx = 0
        for j in range(ny):
            for i in range(nx):
                new_f.paste(blocks[idx], (i * block_size, j * block_size))
                idx += 1
        
        frames.append(new_f)
        durations.append(frame.info.get('duration', 100))

    output = io.BytesIO()
    # 保存为 GIF
    frames[0].save(
        output, 
        format='GIF', 
        save_all=True, 
        append_images=frames[1:], 
        loop=0, 
        duration=durations,
        disposal=2
    )
    output.seek(0)
    return send_file(output, mimetype='image/gif')
