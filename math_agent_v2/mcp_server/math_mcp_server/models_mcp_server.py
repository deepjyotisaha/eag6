from pydantic import BaseModel
from typing import List

# Input/Output models for tools


class MathInput2Int(BaseModel):
    a: int
    b: int

class MathInputInt(BaseModel):
    a: int

class MathOutputInt(BaseModel):
    result: int

class MathInputString(BaseModel):
    string: str

class MathOutputDict(BaseModel):
    result: dict

class MathInputList(BaseModel):
    list_input: list

class MathOutputFloat(BaseModel):
    result: float


class MathOutputListInt(BaseModel):
    result: list[int]

class MathInputListInt(BaseModel):
    int_list: list[int]

class MathOutputListInt(BaseModel):
    result: list[int]

class DrawOutputDict(BaseModel):
    result: dict

class DrawInput4Int(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

class DrawInput4Int1Str(BaseModel):
    x: int
    y: int
    width: int
    height: int
    text: str

class AddInput(BaseModel):
    a: int
    b: int

class AddOutput(BaseModel):
    result: int

class SqrtInput(BaseModel):
    a: int

class SqrtOutput(BaseModel):
    result: float

class StringsToIntsInput(BaseModel):
    string: str

class StringsToIntsOutput(BaseModel):
    ascii_values: List[int]

class ExpSumInput(BaseModel):
    int_list: List[int]

class ExpSumOutput(BaseModel):
    result: float
