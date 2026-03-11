from flask import Flask, request, send_file
from flask_cors import CORS
from PIL import Image, ImageOps, ImageSequence
import io
import math
import numpy as np

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
@app.route('/slitscan', methods=['POST'])
def slitscan():
    if 'image' not in request.files:
        return "No image uploaded", 400
    
    file = request.files['image']
    try:
        img = Image.open(file)
    except IOError:
         return "Invalid image file", 400

    if not getattr(img, "is_animated", False):
        return "Image must be a GIF", 400

    # 获取参数：错位程度 (1-100)，默认 10
    intensity = int(request.form.get('intensity', 10))
    intensity = max(1, min(100, intensity)) # 限制范围

    frames = []
    durations = []
    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert("RGBA"))
        durations.append(frame.info.get('duration', 100))
    
    num_frames = len(frames)
    w, h = frames[0].size
    
    # 将所有帧转换为 numpy 数组
    frames_np = [np.array(f) for f in frames]
    
    new_frames = []
    for i in range(num_frames):
        new_img_np = np.zeros_like(frames_np[0])
        for y in range(h):
            # 核心逻辑：每一行的时间偏移量
            # 偏移量随行号 y 和强度 intensity 变化
            offset = int((y / h) * intensity * (num_frames - 1))
            frame_idx = (i + offset) % num_frames
            new_img_np[y, :, :] = frames_np[frame_idx][y, :, :]
        
        new_frames.append(Image.fromarray(new_img_np, 'RGBA'))
        
    output = io.BytesIO()
    new_frames[0].save(
        output, 
        format='GIF', 
        save_all=True, 
        append_images=new_frames[1:], 
        loop=0, 
        duration=durations,
        disposal=2 
    )
    output.seek(0)
    return send_file(output, mimetype='image/gif')
