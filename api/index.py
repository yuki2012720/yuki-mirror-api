from flask import Flask, request, send_file
from flask_cors import CORS
from PIL import Image, ImageOps, ImageSequence
import io
import numpy as np

app = Flask(__name__)
CORS(app)


def process_frame(img, mode):
    w, h = img.size
    # 使用 RGBA 模式处理，防止透明背景变黑
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 0))

    if mode == 'left-right':
        mid = (w + 1) // 2
        part = img.crop((0, 0, mid, h))
        mirror = ImageOps.mirror(part)
        canvas.paste(part, (0, 0))
        canvas.paste(mirror, (w - mid, 0))
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


def process_single_frame(frame, threshold):
    data = np.array(frame)
    brightness = np.mean(data[:, :, :3], axis=2)

    for y in range(data.shape[0]):
        mask = brightness[y, :] > threshold
        if np.any(mask):
            row_pixels = data[y, mask, :]
            sort_idx = np.argsort(row_pixels[:, 0])
            data[y, mask, :] = row_pixels[sort_idx]

    return Image.fromarray(data)


def clamp_duration(duration):
    # 浏览器对过小帧间隔支持不好，给一个合理下限
    return max(20, int(duration))


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


@app.route('/melt', methods=['POST'])
def pixel_sort_melt():
    if 'image' not in request.files:
        return "No file", 400

    file = request.files['image']
    img = Image.open(file)
    threshold = int(request.form.get('threshold', 100))

    all_frames = []
    durations = []

    for frame in ImageSequence.Iterator(img):
        all_frames.append(frame.copy().convert("RGBA"))
        durations.append(frame.info.get('duration', 100))

    if len(all_frames) <= 1:
        processed_data = process_single_frame(all_frames[0], threshold)
        output = io.BytesIO()
        processed_data.save(output, format='PNG')
        output.seek(0)
        return send_file(output, mimetype='image/png')

    processed_frames = []

    for frame in all_frames[:60]:
        processed_frame = process_single_frame(frame, threshold)
        processed_frames.append(processed_frame)

    output = io.BytesIO()
    processed_frames[0].save(
        output,
        format='GIF',
        save_all=True,
        append_images=processed_frames[1:],
        loop=0,
        duration=durations[:60],
        disposal=2,
        optimize=False
    )
    output.seek(0)
    return send_file(output, mimetype='image/gif')


@app.route('/gif-speed', methods=['POST'])
def gif_speed():
    if 'image' not in request.files:
        return "No file", 400

    file = request.files['image']
    speed = float(request.form.get('speed', 1.0))

    if speed <= 0:
        return "Invalid speed", 400

    img = Image.open(file)

    if not getattr(img, "is_animated", False):
        return "Please upload an animated GIF", 400

    frames = []
    durations = []

    loop = img.info.get('loop', 0)
    disposal = img.info.get('disposal', 2)
    transparency = img.info.get('transparency')

    for frame in ImageSequence.Iterator(img):
        copied = frame.copy().convert("RGBA")
        frames.append(copied)

        original_duration = int(frame.info.get('duration', img.info.get('duration', 100)) or 100)
        adjusted_duration = clamp_duration(original_duration / speed)
        durations.append(adjusted_duration)

    output = io.BytesIO()

    save_kwargs = {
        "format": "GIF",
        "save_all": True,
        "append_images": frames[1:],
        "loop": loop,
        "duration": durations,
        "disposal": disposal,
        "optimize": False
    }

    if transparency is not None:
        save_kwargs["transparency"] = transparency

    frames[0].save(output, **save_kwargs)
    output.seek(0)

    return send_file(
        output,
        mimetype='image/gif',
        as_attachment=False,
        download_name=f"speed-{file.filename or 'output.gif'}"
    )


# Vercel 要求的导出
app = app
