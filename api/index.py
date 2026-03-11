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
@app.route('/melt', methods=['POST'])
def pixel_sort_melt():
    if 'image' not in request.files: return "No file", 400
    
    file = request.files['image']
    img = Image.open(file)
    
    # 阈值：决定哪些像素会被“融化”，0-255
    threshold = int(request.form.get('threshold', 100))
    
    frames = []
    durations = []
    
    for frame in ImageSequence.Iterator(img):
        f = frame.convert("RGBA")
        data = np.array(f)
        
        # 提取亮度 (简单灰度化处理)
        brightness = np.sum(data[:, :, :3], axis=2) / 3
        
        # 核心算法：对每一行进行条件排序
        for y in range(data.shape[0]):
            row = data[y, :, :]
            b_row = brightness[y, :]
            
            # 找到亮度超过阈值的区间进行排序
            mask = b_row > threshold
            if np.any(mask):
                # 找出连续的 True 区间并排序（这里简化为全行排序增加鬼畜感）
                indices = np.where(mask)[0]
                if len(indices) > 1:
                    start, end = indices[0], indices[-1]
                    # 按亮度排序该行像素
                    sort_idx = np.argsort(b_row[start:end])
                    data[y, start:end, :] = data[y, start:end, :][sort_idx]
        
        frames.append(Image.fromarray(data))
        durations.append(frame.info.get('duration', 100))

    output = io.BytesIO()
    frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:], loop=0, duration=durations, disposal=2)
    output.seek(0)
    return send_file(output, mimetype='image/gif')
