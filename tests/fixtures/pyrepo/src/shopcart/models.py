from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel


@dataclass
class Item:  # @model-item
    sku: str
    price: float


class Status(Enum):  # @model-status
    OPEN = 1


class Order(BaseModel):  # @model-order
    items: list[Item]  # @field-items
    status: Status
