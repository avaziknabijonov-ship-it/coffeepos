"""Branch-aware stock levels.

The default branch keeps its quantities on Ingredient.stock/min (historical
schema). Other branches keep one BranchStock row per ingredient.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import default_branch
from .db import BranchStock, Ingredient


def is_default(db: Session, cid: int, branch_id: int | None) -> bool:
    return branch_id is None or branch_id == default_branch(db, cid).id


def row(db: Session, cid: int, branch_id: int, key: str, lock: bool = False) -> BranchStock:
    q = select(BranchStock).where(BranchStock.company_id == cid, BranchStock.branch_id == branch_id,
                                  BranchStock.ingredient == key)
    found = db.scalar(q.with_for_update() if lock else q)
    if found is None:
        found = BranchStock(company_id=cid, branch_id=branch_id, ingredient=key, qty=0.0, min=0.0)
        db.add(found)
        db.flush()
    return found


def levels(db: Session, cid: int, branch_id: int | None) -> dict[str, dict]:
    """{ingredient key: {"stock": qty, "min": threshold}} for one branch."""
    ingredients = db.scalars(select(Ingredient).where(Ingredient.company_id == cid).order_by(Ingredient.id)).all()
    if is_default(db, cid, branch_id):
        return {i.key: {"stock": i.stock, "min": i.min} for i in ingredients}
    stored = {r.ingredient: r for r in db.scalars(select(BranchStock).where(
        BranchStock.company_id == cid, BranchStock.branch_id == branch_id))}
    return {i.key: {"stock": stored[i.key].qty if i.key in stored else 0.0,
                    "min": stored[i.key].min if i.key in stored else 0.0} for i in ingredients}


def get(db: Session, cid: int, branch_id: int | None, ingredient: Ingredient, lock: bool = False) -> float:
    if is_default(db, cid, branch_id):
        return ingredient.stock
    return row(db, cid, branch_id, ingredient.key, lock).qty


def adjust(db: Session, cid: int, branch_id: int | None, ingredient: Ingredient, delta: float) -> float:
    if is_default(db, cid, branch_id):
        ingredient.stock += delta
        return ingredient.stock
    target = row(db, cid, branch_id, ingredient.key, lock=True)
    target.qty += delta
    return target.qty


def set_min(db: Session, cid: int, branch_id: int | None, ingredient: Ingredient, minimum: float) -> None:
    if is_default(db, cid, branch_id):
        ingredient.min = minimum
    else:
        row(db, cid, branch_id, ingredient.key, lock=True).min = minimum
