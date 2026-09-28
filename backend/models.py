from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class Goal(Model):
    name: str = Field(min_length=1, max_length=80)
    target: float = Field(gt=0, le=1e12, multiple_of=0.01)
    saved: float = Field(ge=0, le=1e12, multiple_of=0.01)
    deadline: date | None = None


class Transaction(Model):
    description: str = Field(min_length=1, max_length=180)
    amount: float = Field(gt=0, le=1e10, multiple_of=0.01)
    date: date
    kind: Literal['income', 'expense']
    group: str = Field(min_length=1, max_length=80)
    note: str = Field(default='', max_length=500)
    competence: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    is_salary: bool = False


class TransactionOverride(Model):
    cycle: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    competence: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    kind: Literal['income', 'expense', 'refund', 'other'] | None = None
    is_salary: bool = False


class BudgetLine(Model):
    nome: str = Field(min_length=1, max_length=80)
    teto: float = Field(ge=0, le=1e10, multiple_of=0.01)
    grupos: list[str] = Field(max_length=30)


class Budget(Model):
    salary_next_month: bool = True
    salary_cutoff_day: int = Field(default=25, ge=1, le=31)
    lines: list[BudgetLine] = Field(min_length=1, max_length=40)
    monthly_income: float = Field(ge=0, le=1e10, multiple_of=0.01)
    monthly_saving: float = Field(ge=0, le=1e10, multiple_of=0.01)
    benefits_spending: float = Field(ge=0, le=1e10, multiple_of=0.01)

    @field_validator('lines')
    @classmethod
    def unique_groups(cls, lines):
        groups = [g for line in lines for g in line.grupos]
        if len(groups) != len(set(groups)):
            raise ValueError('Um grupo não pode aparecer em dois limites.')
        return lines


class Position(Model):
    name: str = Field(min_length=1, max_length=120)
    institution: str = Field(min_length=1, max_length=80)
    balance: float = Field(ge=0, le=1e12, multiple_of=0.01)
    reference: date
    asset_class: str = Field(default='Declarado', min_length=1, max_length=80)
