import asyncio
import functools
from io import BytesIO
from urllib.parse import urlencode

import httpx
from PIL import Image, ImageDraw
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.templating import Jinja2Templates

app = Starlette()
templates = Jinja2Templates(directory=".")
overlays = [None] + [Image.open(f"overlays/overlay{x}.png") for x in range(1, 10)]


def run_in_executor(_func):
    @functools.wraps(_func)
    def wrapped(*args, **kwargs):
        loop = asyncio.get_event_loop()
        func = functools.partial(_func, *args, **kwargs)
        return loop.run_in_executor(executor=None, func=func)

    return wrapped


@run_in_executor
def make_image(im, overlay):
    im = im.convert("RGBA")
    w, h = im.size
    if w != h:
        raise TypeError("Image must be square")

    im = im.resize((w * 4, h * 4), resample=Image.NEAREST)
    w, h = im.size

    d = ImageDraw.Draw(im)
    d.ellipse((524 / 1024 * w, 524 / 1024 * h, 1036 / 1024 * w, 1036 / 1024 * h), (255, 255, 255, 0))
    d.rectangle((780 / 1024 * w, 780 / 1024 * h, 1036 / 1024 * w, 1036 / 1024 * h), (255, 255, 255, 0))

    im = im.resize((w // 4, h // 4))
    w, h = im.size

    resized_overlay = overlay.resize((w, h))
    im.alpha_composite(resized_overlay)
    return im


@app.route("/image", methods=["POST"])
async def image(request):
    form = await request.form()

    try:
        url = form["url"]
        idx = int(form.get("idx", "1"))
        if not 1 <= idx <= 9:
            raise ValueError("Invalid idx")
    except (KeyError, ValueError):
        return PlainTextResponse("Bad Request", 400)

    url = "https://little-cherry-0857.oliver-ni.workers.dev/proxy?" + urlencode({"url": url})
    async with httpx.AsyncClient() as client:
        r = await client.get(url)

    if r.status_code != 200:
        return PlainTextResponse("Unable to get image", 500)

    with BytesIO() as fp:
        fp.write(r.content)
        im = Image.open(fp)

        try:
            im = await make_image(im, overlays[idx])
        except TypeError as e:
            return PlainTextResponse(str(e), 400)

    fp = BytesIO()
    im.save(fp, format="PNG")
    fp.seek(0)

    return StreamingResponse(
        fp,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="afdicon.png"'},
    )


@app.route("/", methods=["GET"])
async def index(request):
    return templates.TemplateResponse("index.html", {"request": request})
