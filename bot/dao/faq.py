from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.faq import FAQItem


class FAQItemDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> list[FAQItem]:
        result = await self.session.execute(
            select(FAQItem).order_by(FAQItem.position, FAQItem.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, faq_id: int) -> FAQItem | None:
        result = await self.session.execute(
            select(FAQItem).where(FAQItem.id == faq_id)
        )
        return result.scalar_one_or_none()

    async def create(self, question: str, answer: str) -> FAQItem:
        max_pos_result = await self.session.execute(
            select(func.max(FAQItem.position))
        )
        max_pos = max_pos_result.scalar_one_or_none() or 0
        item = FAQItem(question=question, answer=answer, position=max_pos + 1)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def swap_positions(self, item_a: FAQItem, item_b: FAQItem) -> None:
        item_a.position, item_b.position = item_b.position, item_a.position
        await self.session.commit()

    async def update(self, item: FAQItem, **fields) -> FAQItem:
        for key, value in fields.items():
            setattr(item, key, value)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item: FAQItem) -> None:
        await self.session.delete(item)
        await self.session.commit()
