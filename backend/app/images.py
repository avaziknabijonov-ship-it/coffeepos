"""Manager-only raster uploads; normalized, bounded images live in database backups."""
import io
import re
import secrets
import warnings
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import LargeBinary, String, ForeignKey, func, select
from sqlalchemy.orm import Mapped, mapped_column

from .core import Ctx, MANAGERS, get_db, require
from .db import Base

router = APIRouter()
LIMIT = 3 * 1024 * 1024


class CatalogImage(Base):
    __tablename__ = 'catalog_images'
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), index=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


def validate_image_url(ctx: Ctx, value: str) -> None:
    if not value:
        return
    if value.startswith('/api/images/'):
        row = ctx.db.get(CatalogImage, value.removeprefix('/api/images/'))
        if row is None or row.company_id != ctx.cid:
            raise HTTPException(422, 'Rasm topilmadi')
        return
    parts = urlsplit(value)
    if parts.scheme == 'https' and parts.hostname and not parts.username:
        if parts.hostname in ('share.google', 'photos.app.goo.gl', 'drive.google.com'):
            raise HTTPException(422, 'Rasm faylini qurilmadan yuklang yoki bevosita rasm havolasini kiriting')
        return
    if value.startswith('/assets/') and '..' not in value and not parts.query and not parts.fragment:
        return
    raise HTTPException(422, 'Rasm uchun HTTPS yoki ichki /assets/ manzilini kiriting')


@router.post('/api/images', status_code=201)
async def upload(request: Request, ctx: Ctx = Depends(require(*MANAGERS))):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > LIMIT:
            raise HTTPException(413, 'Rasm hajmi 3 MB dan oshmasin')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 16_000_000:
                    raise ValueError()
                image.load()
                from PIL import ImageOps
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1024, 1024))
                image = image.convert('RGBA')
                output = io.BytesIO()
                image.save(output, format='WEBP', quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Faqat JPG, PNG yoki WebP rasm yuklang') from None
    size = ctx.db.scalar(select(func.coalesce(func.sum(func.length(CatalogImage.data)), 0)).where(CatalogImage.company_id == ctx.cid))
    if size + len(output.getvalue()) > 30 * 1024 * 1024:
        raise HTTPException(413, 'Rasmlar uchun joy to‘ldi')
    row = CatalogImage(id=secrets.token_hex(24), company_id=ctx.cid, data=output.getvalue())
    ctx.db.add(row)
    ctx.db.commit()
    return {'url': '/api/images/' + row.id}


@router.get('/api/images/{key}')
def read_image(key: str, db=Depends(get_db)):
    if not re.fullmatch('[a-f0-9]{48}', key):
        raise HTTPException(404)
    row = db.get(CatalogImage, key)
    if row is None:
        raise HTTPException(404)
    return Response(row.data, media_type='image/webp', headers={'Cache-Control': 'public, max-age=31536000, immutable', 'X-Content-Type-Options': 'nosniff'})
