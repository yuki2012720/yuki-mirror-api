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
    threshold = int(request.form.get('threshold', 100))
    
    frames = []
    durations = []
    
    # --- 加速策略 1：帧数控制 ---
    all_frames = list(ImageSequence.Iterator(img))
    # 如果帧数超过 60 帧，每隔一帧取一次，防止 Vercel 超时
    step = 1 if len(all_frames) < 60 else 2 
    
    for i in range(0, len(all_frames), step):
        frame = all_frames[i]
        # --- 加速策略 2：缩小尺寸处理 ---
        # 如果图太大，强制缩小到 400px 宽，处理完再拉伸（这种“锯齿感”更鬼畜）
        original_size = frame.size
        if original_size[0] > 400:
            frame = frame.resize((400, int(400 * original_size[1] / original_size[0])), Image.NEAREST)
        
        f = frame.convert("RGBA")
        data = np.array(f)
        
        # 简化算法：直接对亮度达标的行进行快速切片排序
        brightness = np.mean(data[:, :, :3], axis=2)
        for y in range(data.shape[0]):
            mask = brightness[y, :] > threshold
            if np.any(mask):
                # 仅对这一行中“亮”的部分进行排序
                row_pixels = data[y, mask, :]
                # 按红色通道排序（比按计算出来的亮度排快得多）
                sort_idx = np.argsort(row_pixels[:, 0])
                data[y, mask, :] = row_pixels[sort_idx]
        
        new_frame = Image.fromarray(data)
        # 如果之前缩小了，现在拉回原大
        if original_size[0] > 400:
            new_frame = new_frame.resize(original_size, Image.NEAREST)
            
        frames.append(new_frame)
        durations.append(img.info.get('duration', 100) * step) # 补偿跳帧的时间

    output = io.BytesIO()
    # --- 加速策略 3：压缩优化 ---
    frames[0].save(
        output, 
        format='GIF', 
        save_all=True, 
        append_images=frames[1:], 
        loop=0, 
        duration=durations,
        optimize=True # 开启保存优化
    )
    output.seek(0)
    return send_file(output, mimetype='image/gif')
