import asyncio
import functools
from io import BytesIO
from urllib.parse import urlencode

import httpx
from PIL import Image, ImageDraw, UnidentifiedImageError
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
    w, h = im.size
    if w != h:
        raise TypeError(f"Image must be square (given: {w} x {h})")

    im = im.resize((w * 4, h * 4), resample=Image.NEAREST)
    w, h = im.size

    d = ImageDraw.Draw(im)
    d.ellipse(
        (524 / 1024 * w, 524 / 1024 * h, 1036 / 1024 * w, 1036 / 1024 * h), (255, 255, 255, 0)
    )
    d.rectangle(
        (780 / 1024 * w, 780 / 1024 * h, 1036 / 1024 * w, 1036 / 1024 * h), (255, 255, 255, 0)
    )

    im = im.resize((w // 4, h // 4))
    w, h = im.size

    resized_overlay = overlay.resize((w, h))
    im.alpha_composite(resized_overlay)
    return im


class ImageFetchError(Exception):
    pass


async def get_im_from_url(url):
    req_url = "https://little-cherry-0857.oliver-ni.workers.dev/proxy?" + urlencode({"url": url})

    async with httpx.AsyncClient() as client:
        r = await client.get(req_url)

    if r.status_code != 200:
        msg = f"Unable to get image. Are you submitting a direct link to a file?\n\nGot response from {url}:\n\n{r.text}"
        raise ImageFetchError(msg)

    with BytesIO() as fp:
        fp.write(r.content)
        try:
            return Image.open(fp).convert("RGBA")
        except UnidentifiedImageError:
            msg = "Could not identify image file. Are you submitting a direct link to a file?"
            raise ImageFetchError(msg)


@app.route("/image", methods=["POST"])
async def image(request):
    form = await request.form()

    idx = int(form.get("idx", "1"))
    if not 1 <= idx <= 9:
        raise ValueError("Invalid idx")

    try:
        im = Image.open(form["file"].file).convert("RGBA")
    except (KeyError, UnidentifiedImageError):
        try:
            url = form["url"]
        except (KeyError, ValueError):
            return PlainTextResponse("Need either url or file", 400)

        try:
            im = await get_im_from_url(url)
        except ImageFetchError as e:
            return PlainTextResponse(str(e), 422)

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
