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
    
    # --- 强力修复：物理提取所有帧 ---
    all_frames = []
    durations = []
    
    # 即使是只有一帧的图，ImageSequence 也能处理
    for frame in ImageSequence.Iterator(img):
        # 使用 .copy() 彻底断绝与原图的引用关系，防止“粘连”
        all_frames.append(frame.copy().convert("RGBA"))
        durations.append(frame.info.get('duration', 100))

    if len(all_frames) <= 1:
        # 如果真的不是动图，直接处理单张返回
        processed_data = process_single_frame(all_frames[0], threshold)
        output = io.BytesIO()
        processed_data.save(output, format='PNG')
        output.seek(0)
        return send_file(output, mimetype='image/png')

    # --- 开始逐帧“手术” ---
    processed_frames = []
    # 限制总帧数，防止 Vercel 炸掉 (选前 60 帧)
    for f in all_frames[:60]:
        data = np.array(f)
        # 简化版排序：速度飞快且稳定
        brightness = np.mean(data[:, :, :3], axis=2)
        for y in range(data.shape[0]):
            mask = brightness[y, :] > threshold
            if np.any(mask):
                row_pixels = data[y, mask, :]
                # 按红色通道排序，产生那种诡异的熔化感
                sort_idx = np.argsort(row_pixels[:, 0])
                data[y, mask, :] = row_pixels[sort_idx]
        
        processed_frames.append(Image.fromarray(data))

    # --- 重新打包，确保 metadata 完整 ---
    output = io.BytesIO()
    processed_frames[0].save(
        output, 
        format='GIF', 
        save_all=True, 
        append_images=processed_frames[1:], 
        loop=0,               # 确保循环播放
        duration=durations[:60], # 保持原有的帧间隔
        disposal=2,           # 每一帧都清理上一帧，防止重影
        optimize=False        # 递归处理时关闭 optimize 有时更稳
    )
    output.seek(0)
    return send_file(output, mimetype='image/gif')

# 辅助函数，处理非 GIF 情况
def process_single_frame(f, threshold):
    data = np.array(f)
    brightness = np.mean(data[:, :, :3], axis=2)
    for y in range(data.shape[0]):
        mask = brightness[y, :] > threshold
        if np.any(mask):
            row_pixels = data[y, mask, :]
            sort_idx = np.argsort(row_pixels[:, 0])
            data[y, mask, :] = row_pixels[sort_idx]
    return Image.fromarray(data)
    output.seek(0)
    return send_file(output, mimetype='image/gif')
