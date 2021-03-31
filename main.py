from starlette.templating import Jinja2Templates
from io import BytesIO
import asyncio
import functools
import httpx

from PIL import Image, ImageDraw
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, StreamingResponse


app = Starlette()
templates = Jinja2Templates(directory=".")
overlay = Image.open("overlay.png")


def run_in_executor(_func):
    @functools.wraps(_func)
    def wrapped(*args, **kwargs):
        loop = asyncio.get_event_loop()
        func = functools.partial(_func, *args, **kwargs)
        return loop.run_in_executor(executor=None, func=func)

    return wrapped


@run_in_executor
def make_image(im):
    im = im.convert("RGBA")
    w, h = im.size
    if w != h:
        raise TypeError("Image must be square")

    d = ImageDraw.Draw(im)
    d.ellipse((205 / 400 * w, 205 / 400 * h, 405 / 400 * w, 405 / 400 * h), (255, 255, 255, 0))
    d.rectangle((305 / 400 * w, 305 / 400 * h, 405 / 400 * w, 405 / 400 * h), (255, 255, 255, 0))

    resized_overlay = overlay.resize((w, h))
    im.alpha_composite(resized_overlay)
    return im


@app.route("/image", methods=["POST"])
async def image(request):
    form = await request.form()

    try:
        url = form["url"]
    except KeyError:
        return PlainTextResponse("Must provide URL", 400)

    async with httpx.AsyncClient() as client:
        r = await client.get(url)

    if r.status_code != 200:
        return PlainTextResponse("Unable to get image", 500)

    with BytesIO() as fp:
        fp.write(r.content)
        im = Image.open(fp)

        try:
            im = await make_image(im)
        except TypeError as e:
            return PlainTextResponse(str(e), 400)

    fp = BytesIO()
    im.save(fp, format="PNG")
    fp.seek(0)
    return StreamingResponse(fp, media_type="image/png")


@app.route("/", methods=["GET"])
async def index(request):
    return templates.TemplateResponse("index.html", {"request": request})