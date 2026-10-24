# -*- coding: utf-8 -*-
"""批号解析 / 排序 / 年份识别（移植自旧工具 components/batch_utils.py，逻辑不变）。"""
import re

import numpy as np
import pandas as pd


def extract_batch_order(batch_number):
    """
    批号排序键（统一规则）：
      1) 去掉末尾所有英文字母；2) 继续剥离末尾非数字字符；
      3) 取末尾连续数字串；4) >8 位取后 8 位；长度为 6 或 8 才有效，否则返回 0。

    Examples
    --------
    >>> extract_batch_order('007-201903F')
    201903
    >>> extract_batch_order('PG1B20201104')
    20201104
    >>> extract_batch_order('NP520250501A')
    20250501
    >>> extract_batch_order('bad')
    0
    """
    if not isinstance(batch_number, str) or not batch_number.strip():
        return 0

    s = batch_number.strip().upper()
    s = re.sub(r"[A-Z]+$", "", s)
    s = re.sub(r"[^0-9]+$", "", s)

    m = re.search(r"(\d+)$", s)
    if not m:
        return 0

    num = m.group(1)
    if len(num) > 8:
        num = num[-8:]

    if len(num) in (6, 8):
        try:
            return int(num)
        except Exception:
            return 0
    return 0


def extract_year_from_batch(batch_number):
    """
    通过排序键反推年份：8 位 YYYYMMNN → key//10000；6 位 YYYYNN → key//100；无效→NaN。

    Examples
    --------
    >>> extract_year_from_batch('007-201903F')
    2019
    >>> extract_year_from_batch('PG1B20201104')
    2020
    """
    key = extract_batch_order(batch_number)
    if not isinstance(key, (int, np.integer)) or key <= 0:
        return np.nan
    if key >= 10**7:
        return key // 10000
    elif key >= 10**5:
        return key // 100
    return np.nan


def sort_batch_list(lots):
    """返回按业务规则排序后的批号列表。"""
    return sorted(list(lots), key=extract_batch_order)


def attach_sort_key(df: pd.DataFrame, lot_col: str = "batch_number") -> pd.DataFrame:
    """给 DataFrame 添加 lot_sort_key（批号排序整数键）。"""
    df = df.copy()
    df["lot_sort_key"] = df[lot_col].apply(extract_batch_order)
    return df


def attach_year(df: pd.DataFrame, lot_col: str = "batch_number") -> pd.DataFrame:
    """给 DataFrame 添加 year（从批号反推年份）。"""
    df = df.copy()
    df["year"] = df[lot_col].apply(extract_year_from_batch)
    return df
